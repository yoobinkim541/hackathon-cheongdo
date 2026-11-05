---
id: T02
title: 인프라 코드와 빈 앱 배포 준비
sprint: S0
priority: P0
cut_rank: 0
deps: [T00]
owns: [infra/, azure.yaml, Dockerfile, .dockerignore, .gitignore]
verify: ["python -c \"import pathlib,sys; need=['infra/main.bicep','azure.yaml','Dockerfile','.gitignore']; miss=[p for p in need if not pathlib.Path(p).exists()]; print(miss); sys.exit(1 if miss else 0)\"", "python -c \"import pathlib,sys; g=pathlib.Path('.gitignore').read_text(encoding='utf-8'); sys.exit(0 if '.azure/' in g else 1)\""]
features: []
flag: null
---

# T02 — 인프라

## 목표

`azd up` 한 번으로 TRD 6절의 리소스를 만들고 컨테이너를 배포할 수 있는 Bicep·`azure.yaml`·Dockerfile을 만든다. 배포 실행은 오케스트레이터가 한다(워커는 배포 명령을 실행하지 않는다).

## 근거

- TRD 2절(Docker 런타임 내려받기), 6절 전체와 표 7
- 스파인 AD-14, AD-15, 배포 다이어그램
- SPRINTS.md 4절(Bicep 매개변수로 켜는 플래그)

## 계약

- `infra/main.bicep` 매개변수: `environmentName`, `location`, `copilotGithubToken`(`@secure`), `copilotModel`, `enableAiServices`(기본 `false`), `enableAvailabilityTest`(기본 `false`), 그리고 SPRINTS.md 4절 앱 플래그 10개(`string`, 기본 `'false'`)를 Container App 환경변수로 그대로 넘긴다.
- 모듈 분리: `infra/modules/aiservices.bicep`(조건부), `infra/modules/availability.bicep`(조건부, 내용은 T23이 채우고 이 태스크는 빈 모듈과 조건부 참조만 둔다).
- 출력: `AZURE_CONTAINER_REGISTRY_ENDPOINT`, `SERVICE_WEB_URI`, `AZURE_AI_ENDPOINT`(꺼져 있으면 빈 문자열).
- `azure.yaml`: 서비스 하나(`web`, `host: containerapp`, `language: python`, Dockerfile 사용).
- Dockerfile: `python:3.12-slim`, 비root 사용자, 쓰기 가능한 `HOME`, `COPILOT_CLI_EXTRACT_DIR=/opt/copilot-runtime`, 빌드 단계 `python -m copilot download-runtime`, 실행 `COPILOT_SKIP_CLI_DOWNLOAD=1`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `.gitignore`: `.azure/`, `__pycache__/`, `.pytest_cache/`, `.venv/`, `*.pyc`. 에이전트 도구 디렉터리는 넣지 않는다(AGENTS.md 3절).

## 동작

- Container App: 단일 리비전 모드, 최소·최대 복제본 1, 1 vCPU / 2 GiB, 외부 ingress 8000, liveness `/healthz`, readiness `/readyz`.
- 사용자 할당 관리 ID 하나와 역할 할당 3개(`AcrPull`, `Key Vault Secrets User`, `Cognitive Services User`는 `enableAiServices`일 때만)를 Container App보다 먼저 만들고 `dependsOn`한다. `AZURE_CLIENT_ID`에 관리 ID의 clientId를 넣는다.
- Key Vault(RBAC 모드)에 `copilot-github-token` 비밀을 쓰고, Container App secret은 `keyVaultUrl` + `identity`로 참조한다.
- Log Analytics 작업 영역 하나를 Container Apps 환경과 Application Insights가 함께 쓴다.
- AI Services: `kind: AIServices`, 사용자 지정 하위 도메인, `disableLocalAuth: true`.

## 수용 기준

- verify 명령이 통과한다(필수 파일, `.azure/` 무시).
- `az bicep build --file infra/main.bicep`가 오류 없이 끝난다(오케스트레이터가 G0에서 확인).
- G0: 오케스트레이터가 `enableAiServices=false`로 `azd up` → 공개 URL `/healthz` 200. 직후 `enableAiServices=true`로 다시 `azd up`해 역할 전파 시간을 번다(TRD 6절).
- 저장소에 토큰·키를 두지 않는다.

## 하지 않는 것

- `azd up` 실행, 가용성 테스트 본문(T23), 앱 코드.
