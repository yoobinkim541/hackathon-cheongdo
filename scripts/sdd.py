"""SDD 태스크 조회·선점·검증 도구.

상태는 저장소 밖(공통 git 디렉터리 아래 sdd-state/)에 둔다. 저장소 파일은 바꾸지 않는다.

사용법:
  python scripts/sdd.py list                 전체 상태
  python scripts/sdd.py ready                지금 잡을 수 있는 태스크(우선순위 순)
  python scripts/sdd.py show T03             태스크 frontmatter
  python scripts/sdd.py claim T03 --worker w1
  python scripts/sdd.py check T03            verify 명령 실행 + 소유 파일 확인
  python scripts/sdd.py done T03
  python scripts/sdd.py block T03 "이유"
  python scripts/sdd.py release T03          선점·막힘 해제(todo로)
  python scripts/sdd.py lint                 태스크 문서 정합성(의존·순환·소유 겹침)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "docs" / "sdd" / "tasks"
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass
class Task:
    id: str
    title: str
    path: Path
    sprint: str = ""
    priority: str = "P3"
    cut_rank: int = 0
    deps: list[str] = field(default_factory=list)
    owns: list[str] = field(default_factory=list)
    verify: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    flag: str | None = None


def _parse_value(raw: str):
    raw = raw.strip()
    if " #" in raw and not raw.startswith(("[", '"')):
        raw = raw.split(" #", 1)[0].strip()
    if raw in ("null", "~", ""):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    return raw.strip("'\"")


def load_tasks() -> dict[str, Task]:
    tasks: dict[str, Task] = {}
    for path in sorted(TASK_DIR.glob("T*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise SystemExit(f"frontmatter 없음: {path.name}")
        meta: dict = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line or line.startswith(" "):
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = _parse_value(value)
        task = Task(
            id=str(meta["id"]),
            title=str(meta.get("title", "")),
            path=path,
            sprint=str(meta.get("sprint", "")),
            priority=str(meta.get("priority", "P3")),
            cut_rank=int(meta.get("cut_rank") or 0),
            deps=list(meta.get("deps") or []),
            owns=[p.replace("\\", "/") for p in (meta.get("owns") or [])],
            verify=list(meta.get("verify") or []),
            features=list(meta.get("features") or []),
            flag=meta.get("flag"),
        )
        if task.id in tasks:
            raise SystemExit(f"태스크 ID 중복: {task.id}")
        tasks[task.id] = task
    return tasks


# ---------------------------------------------------------------- 상태 저장소


def state_dir() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    common = Path(out)
    if not common.is_absolute():
        common = (ROOT / common).resolve()
    d = common / "sdd-state"
    (d / "claims").mkdir(parents=True, exist_ok=True)
    (d / "done").mkdir(parents=True, exist_ok=True)
    return d


class Mutex:
    """mkdir 기반 전역 잠금. 여러 워커가 동시에 선점해도 한 명만 통과한다."""

    def __init__(self, base: Path):
        self.path = base / ".mutex"

    def __enter__(self):
        for _ in range(200):
            try:
                self.path.mkdir()
                return self
            except FileExistsError:
                if time.time() - self.path.stat().st_mtime > 30:
                    self.path.rmdir()
                    continue
                time.sleep(0.05)
        raise SystemExit("잠금을 얻지 못했습니다. 잠시 뒤 다시 시도하세요.")

    def __exit__(self, *exc):
        self.path.rmdir()


def status_of(sd: Path, task_id: str) -> dict:
    if (sd / "done" / task_id).exists():
        return {"status": "done"}
    claim = sd / "claims" / task_id
    if claim.exists():
        info = json.loads((claim / "info.json").read_text(encoding="utf-8"))
        if (claim / "blocked").exists():
            info["status"] = "blocked"
            info["reason"] = (claim / "blocked").read_text(encoding="utf-8")
        else:
            info["status"] = "claimed"
        return info
    return {"status": "todo"}


# ---------------------------------------------------------------- 그래프


def ancestors(tasks: dict[str, Task], task_id: str) -> set[str]:
    seen: set[str] = set()
    stack = list(tasks[task_id].deps)
    while stack:
        dep = stack.pop()
        if dep in seen or dep not in tasks:
            continue
        seen.add(dep)
        stack.extend(tasks[dep].deps)
    return seen


def overlaps(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.endswith("/") and b.startswith(a):
        return True
    if b.endswith("/") and a.startswith(b):
        return True
    return False


def owned_conflicts(t1: Task, t2: Task) -> list[tuple[str, str]]:
    return [(a, b) for a in t1.owns for b in t2.owns if overlaps(a, b)]


def ready_list(tasks: dict[str, Task], sd: Path) -> list[Task]:
    statuses = {tid: status_of(sd, tid)["status"] for tid in tasks}
    active = [tasks[t] for t, s in statuses.items() if s in ("claimed", "blocked")]
    out = []
    for task in tasks.values():
        if statuses[task.id] != "todo":
            continue
        if any(statuses.get(d) != "done" for d in task.deps):
            continue
        if any(owned_conflicts(task, other) for other in active):
            continue
        out.append(task)
    out.sort(key=lambda t: (PRIORITY_ORDER.get(t.priority, 9), -t.cut_rank, t.id))
    return out


# ---------------------------------------------------------------- 명령


def cmd_list(tasks, sd, _args):
    for task in tasks.values():
        st = status_of(sd, task.id)
        extra = ""
        if st["status"] in ("claimed", "blocked"):
            extra = f" [{st.get('worker', '?')}]"
        if st["status"] == "blocked":
            extra += f" 이유: {st.get('reason', '')}"
        print(f"{task.id} {st['status']:<8} {task.sprint:<3} {task.priority} {task.title}{extra}")


def cmd_ready(tasks, sd, _args):
    for task in ready_list(tasks, sd):
        print(f"{task.id} {task.priority} cut={task.cut_rank} {task.title}")


def cmd_show(tasks, _sd, args):
    task = _get(tasks, args)
    for key in ("id", "title", "sprint", "priority", "cut_rank", "deps", "owns", "verify", "features", "flag"):
        print(f"{key}: {getattr(task, key)}")
    print(f"path: {task.path.relative_to(ROOT).as_posix()}")


def cmd_claim(tasks, sd, args):
    task = _get(tasks, args)
    worker = "anon"
    if "--worker" in args:
        worker = args[args.index("--worker") + 1]
    with Mutex(sd):
        if task not in ready_list(tasks, sd):
            st = status_of(sd, task.id)["status"]
            raise SystemExit(f"{task.id}을(를) 잡을 수 없습니다(상태 {st}, 의존 미완료 또는 소유 파일 잠김).")
        claim = sd / "claims" / task.id
        claim.mkdir()
        (claim / "info.json").write_text(
            json.dumps({"worker": worker, "claimed_at": time.strftime("%H:%M:%S")}),
            encoding="utf-8",
        )
    print(f"{task.id} 선점: {task.title}")
    print(f"명세: {task.path.relative_to(ROOT).as_posix()}")
    print("소유 파일: " + ", ".join(task.owns))


def _run_verify(task: Task) -> bool:
    ok = True
    for cmd in task.verify:
        line = cmd
        if line.startswith("python "):
            line = f'"{sys.executable}" ' + line[len("python "):]
        print(f"$ {cmd}")
        result = subprocess.run(line, cwd=ROOT, shell=True)
        if result.returncode != 0:
            print(f"실패: {cmd} (종료 코드 {result.returncode})")
            ok = False
    return ok


def cmd_check(tasks, sd, args):
    task = _get(tasks, args)
    ok = True
    for dep in task.deps:
        if status_of(sd, dep)["status"] != "done":
            print(f"의존 미완료: {dep}")
            ok = False
    for owned in task.owns:
        if not (ROOT / owned).exists():
            print(f"소유 파일 없음: {owned}")
            ok = False
    ok = _run_verify(task) and ok
    print("check 통과" if ok else "check 실패")
    sys.exit(0 if ok else 1)


def cmd_done(tasks, sd, args):
    task = _get(tasks, args)
    claim = sd / "claims" / task.id
    if not claim.exists():
        raise SystemExit(f"{task.id}은(는) 선점되지 않았습니다.")
    if "--skip-verify" not in args and not _run_verify(task):
        raise SystemExit("verify 실패: done 처리하지 않습니다.")
    with Mutex(sd):
        info = json.loads((claim / "info.json").read_text(encoding="utf-8"))
        info["done_at"] = time.strftime("%H:%M:%S")
        (sd / "done" / task.id).write_text(json.dumps(info), encoding="utf-8")
        _rmtree(claim)
    print(f"{task.id} 완료")


def cmd_block(tasks, sd, args):
    task = _get(tasks, args)
    reason = " ".join(a for a in args[1:] if a != task.id) or "이유 없음"
    claim = sd / "claims" / task.id
    if not claim.exists():
        raise SystemExit(f"{task.id}은(는) 선점되지 않았습니다.")
    (claim / "blocked").write_text(reason, encoding="utf-8")
    print(f"{task.id} 막힘: {reason}")


def cmd_release(tasks, sd, args):
    task = _get(tasks, args)
    claim = sd / "claims" / task.id
    if claim.exists():
        _rmtree(claim)
    print(f"{task.id} 해제")


def cmd_lint(tasks, _sd, _args):
    problems = []
    for task in tasks.values():
        for dep in task.deps:
            if dep not in tasks:
                problems.append(f"{task.id}: 없는 의존 {dep}")
        if task.id in ancestors(tasks, task.id):
            problems.append(f"{task.id}: 순환 의존")
        if not task.verify:
            problems.append(f"{task.id}: verify 없음")
    ids = sorted(tasks)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            conflicts = owned_conflicts(tasks[a], tasks[b])
            if not conflicts:
                continue
            if a in ancestors(tasks, b) or b in ancestors(tasks, a):
                continue
            pairs = ", ".join(f"{x}~{y}" for x, y in conflicts)
            problems.append(f"{a}·{b}: 순서 없는 소유 겹침 {pairs}")
    for p in problems:
        print(p)
    print(f"태스크 {len(tasks)}개, 문제 {len(problems)}개")
    sys.exit(1 if problems else 0)


def _get(tasks, args) -> Task:
    if not args:
        raise SystemExit("태스크 ID가 필요합니다.")
    task_id = args[0].upper()
    if task_id not in tasks:
        raise SystemExit(f"없는 태스크: {task_id}")
    return tasks[task_id]


def _rmtree(path: Path):
    for child in path.iterdir():
        child.unlink()
    path.rmdir()


COMMANDS = {
    "list": cmd_list,
    "ready": cmd_ready,
    "show": cmd_show,
    "claim": cmd_claim,
    "check": cmd_check,
    "done": cmd_done,
    "block": cmd_block,
    "release": cmd_release,
    "lint": cmd_lint,
}


def main(argv: list[str]) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    tasks = load_tasks()
    sd = state_dir() if argv[0] != "lint" else Path()
    COMMANDS[argv[0]](tasks, sd, argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
