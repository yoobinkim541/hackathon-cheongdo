"""Record saved runs for the demo cases by running the real workflow locally.

Usage: COPILOT_GITHUB_TOKEN=... python -m scripts.record_replay [case_id ...]
Writes data/replays/<case_id>.json (events up to the approval request plus a state snapshot).
"""

from __future__ import annotations

import asyncio
import sys

from app.service import REPLAY_DIR, SERVICE, load_cases


async def main(case_ids: list[str]) -> int:
    await SERVICE.startup()
    if not SERVICE.readiness.copilot_ready:
        print("Copilot is not ready; cannot record.", file=sys.stderr)
        return 1
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for case_id in case_ids or list(load_cases()):
        try:
            replay = await SERVICE.record_replay(case_id)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"{case_id}: failed ({exc})", file=sys.stderr)
            continue
        (REPLAY_DIR / f"{case_id}.json").write_text(replay.model_dump_json(indent=1), encoding="utf-8")
        print(f"{case_id}: {len(replay.events)} events")
    await SERVICE.shutdown()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
