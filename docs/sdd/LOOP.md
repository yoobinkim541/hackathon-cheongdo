# 자동화 루프

워커와 오케스트레이터가 쓰는 지시문이다. 아래 블록을 그대로 에이전트 세션에 붙여 넣는다. `<WORKER>`는 워커마다 다른 짧은 이름(예: `w1`)으로 바꾼다. 이 이름은 저장소 밖 선점 상태에만 남는다.

## 1. 워커 루프

```text
너는 동행노트 저장소의 워커 <WORKER>다. 아래 루프를 태스크가 없을 때까지 반복한다.

1. 고르기
   python scripts/sdd.py ready 를 실행해 첫 줄의 태스크 ID를 고른다.
   목록이 비어 있으면 python scripts/sdd.py list 로 진행 상황을 보고 3분 기다린 뒤 다시 한다.
   10번 연속 비어 있으면 루프를 끝낸다.

2. 선점
   python scripts/sdd.py claim <ID> --worker <WORKER>
   실패하면(다른 워커가 먼저 잡았거나 파일이 잠김) 1로 돌아가 다음 태스크를 고른다.

3. 명세 읽기
   docs/sdd/tasks/<ID>-*.md 를 읽고, "근거"에 적힌 TRD·스파인 절을 읽는다.
   docs/sdd/README.md 3절 규칙을 다시 확인한다.

4. 테스트 먼저
   "수용 기준"을 frontmatter owns 안의 테스트 파일로 옮긴다. 아직 구현되지 않은
   다른 태스크의 모듈은 import는 하되 monkeypatch나 tests/fakes.py의 가짜로 바꾼다.
   python -m pytest -q <내 테스트 파일> 이 실패하는 것을 확인한다.

5. 구현
   owns에 있는 파일만 고친다. 다른 파일을 고쳐야 하면 고치지 말고
   docs/sdd/requests/<ID>-<짧은이름>.md 를 쓰고
   python scripts/sdd.py block <ID> "요청: <파일 이름>" 을 실행한 뒤 1로 돌아간다.
   app/schemas.py, app/config.py, requirements.txt 는 T00이 아니면 절대 고치지 않는다.

6. 검증
   python scripts/sdd.py check <ID>
   실패하면 5로 돌아간다. 같은 실패가 3번 반복되면
   python scripts/sdd.py block <ID> "<실패 요약 한 줄>" 후 1로 돌아간다.

7. 완료
   python scripts/sdd.py done <ID>
   바꾼 파일 목록과 수용 기준 충족 여부를 3줄 이내로 보고하고 1로 돌아간다.

지키는 것:
- git commit, git push, git stash, git checkout -- , git reset, git clean 을 실행하지 않는다.
  다른 워커의 작업 중인 파일이 같은 작업 트리에 있다.
- azd, az, 배포 명령을 실행하지 않는다(T02·T23은 Bicep·스크립트 작성까지만).
- 플래그 기본값(app/config.py)을 바꾸지 않는다. 기능은 플래그가 켜졌을 때만 동작하게 만든다.
- 저장소 파일·주석에 에이전트·도구·모델 이름, 세션 ID, 로컬 절대 경로를 쓰지 않는다.
- 다른 테스트 파일이 실패해도 내 owns 밖이면 고치지 않는다. check는 내 verify 명령만 본다.
- 사용자 유래 텍스트를 모델에 보내는 코드는 반드시 masking.mask()를 거친다(AD-11).
```

## 2. 오케스트레이터 루프

```text
너는 동행노트 저장소의 오케스트레이터다. 워커는 코드를, 너는 게이트·배포·계약을 맡는다.
5분마다 아래를 반복한다.

1. python scripts/sdd.py list 로 상태를 본다. blocked 태스크의 이유를 읽는다.
2. docs/sdd/requests/ 에 파일이 있으면 하나씩 처리한다.
   - app/schemas.py·app/config.py·requirements.txt 변경이면 직접 반영하고,
     TRD·스파인과 어긋나면 그 문서도 같은 변경으로 고친다.
   - 처리한 요청 파일을 지우고 python scripts/sdd.py release <ID> 로 태스크를 푼다.
3. 현재 시각이 docs/sdd/SPRINTS.md 2절 게이트 시각이면 그 게이트 확인 항목을 실행한다.
   - 전체 테스트: python -m pytest -q
   - 배포: azd up (플래그는 azd env set 으로 바꾼다)
   - 배포 앱 확인: 사례 1 라이브 실행, 승인·거부
   - 통과한 기능의 플래그를 켜고, 회귀가 나면 그 플래그만 끈다.
4. 게이트를 통과하면 사람이 커밋하도록 알린다(커밋은 직접 하지 않는다).
5. P0 태스크가 15분 넘게 claimed 상태면 워커에게 진행 상황을 묻거나
   release 후 다시 배정한다.
```

## 3. 루프 시작 순서

1. 오케스트레이터가 `python scripts/sdd.py lint`(문제 0개)와 `python scripts/sdd.py list`(25개)를 확인한다.
2. 환경: 가상환경은 저장소 밖에 만든다(예: 홈 디렉터리 아래). T00이 `requirements-dev.txt`를 만든 뒤 각 워커가 같은 가상환경에 `pip install -r requirements-dev.txt`를 한 번 한다. 이후 `python`은 그 가상환경의 인터프리터를 뜻한다.
3. 워커 하나가 T00을 잡는다. T00이 끝나기 전에는 T01만 같이 진행할 수 있다(`ready`가 그렇게 내준다).
4. T00이 `done`이 되면 워커를 4~6개로 늘린다. S1은 독립 태스크가 6개라 그 이상은 놀게 된다.
5. 사람 작업(촬영·녹음, Azure 로그인, 토큰)은 루프와 병렬로 한다.

## 4. 검증 명령 규칙

- 모든 `verify` 명령은 저장소 루트에서 실행한다. 네트워크·Azure·Copilot 토큰이 없어도 통과해야 한다. 실제 호출을 확인하는 항목은 "배포 확인"으로 분리해 오케스트레이터가 게이트에서 본다.
- 테스트는 `tests/conftest.py`(T00)의 `REGISTRY.clear()` 자동 픽스처로 서로 격리된다.
- 각 태스크의 테스트 파일 이름은 겹치지 않는다(`tests/test_<모듈>.py`).
