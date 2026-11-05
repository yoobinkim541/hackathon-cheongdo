# 동행노트

읍·면 행정복지센터 맞춤형복지팀 담당자가 가정 방문 상담 메모를 입력하거나 손글씨 메모 사진·상담 녹음을 올리면, 이를 텍스트로 바꾸고 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱이다. 의뢰서는 담당자가 승인해야만 확정된다. 2026 청도 바이브코딩 해커톤 출품작이다.

- 제품 요구사항: [PRD.md](./PRD.md)
- 기술 설계: [TRD.md](./TRD.md), 요약 명세: [SPEC.md](./SPEC.md)
- API·SSE·보안 명세: [docs/api.md](./docs/api.md)
- 라이브러리 명세 정리: [GitHub Copilot SDK](./docs/reference/copilot-sdk.md), [Microsoft Agent Framework](./docs/reference/agent-framework.md)
- 평가 실행 결과: [docs/eval-result.md](./docs/eval-result.md)

## 심사자 30초 경로

1. 배포 URL `https://ca-web-7fdjs3dl7icwm.politebay-c02184a7.koreacentral.azurecontainerapps.io/`을 연다. 로그인은 없다.
2. "데모 사례로 시작"을 누르고 사례 목록에서 "이 사례로 실행"을 누른다. 라이브 실행은 입력부터 승인 대기까지 약 40초다(평균 40.6초). Copilot이 준비되지 않았거나 실행이 실패하면 같은 사례가 "저장된 실행 재생" 배지와 함께 자동으로 재생된다.
3. 타임라인에서 단계별 진행, 쉬운 한국어 도구 호출 칩(예: "기초연금 → 해당 없음"), 단계별 "에이전트 설명 보기"를 확인한다.
4. "의뢰서 확정" → 승인 창에서 "승인"을 누르면 확정 문서와 담당자 검토 시간이 표시된다.
5. 상태 확인: `/readyz`(Copilot·AI Services 준비 상태), `/api/features`(사진·음성·브라우저 녹음 사용 가능 여부).
6. 화면에 `run_not_found`가 보이면 재배포·재시작으로 메모리의 실행이 사라진 것이다. "데모 사례로 시작"부터 새로 시작한다(실행 상태는 단일 복제본의 프로세스 메모리에만 있다).
7. 키보드만으로도 진행할 수 있다: Tab으로 "데모 사례로 시작" → 사례의 "이 사례로 실행" → 결과 항목 → "의뢰서 확정" → 승인 창 "승인"(Esc로 닫기). 검증 완료와 확정 시 포커스가 결과 제목으로 옮겨 간다.

## 구성

- Microsoft Agent Framework `WorkflowBuilder`로 입력 분기(텍스트·사진·음성) → 인식(OCR·STT) → 가리기 → 인식 결과 정리 → 사실 구조화 → 분야별 제도 매칭(3개 병렬) → 근거 검증 → 문서 초안 → 승인 요청을 잇는다.
- 모델을 쓰는 단계는 6개(NoteNormalizer, Profiler, 분야별 매칭 3개, Documenter)이며 모두 `GitHubCopilotAgent`다. 공유 `CopilotClient` 하나(`agents.AgentHub`)로 GitHub Copilot SDK 세션을 연다. InputRouter·OCR·STT·Intake(가리기)·Verifier(근거 검증)·ReferralGate(승인)는 모델을 쓰지 않는 코드 실행기다.
- 자격 판정은 규칙 함수(도구)가 하고, 모델은 인식 결과 정리, 판정 입력값 추출, 검사 우선순위 판단, 추가 질문 작성, 문서 초안에만 쓴다. 화면은 판정 결과를 "규칙상 충족"·"확인 필요"·"해당 없음"으로 나누며, "규칙상 충족"은 단순화한 공개 기준에 따른 결과라 담당자가 최종 확인한다.
- 의뢰서 확정은 MAF `request_info`로 멈춘 워크플로에 담당자가 승인 응답을 넣어야만 코드(`render.render_final`)가 실행한다. 모델이 호출할 수 있는 확정 도구는 없다.
- Azure Container Apps, Container Registry, Key Vault, Application Insights, Azure AI Services(Document Intelligence·Speech)에 `azd up`으로 배포한다. 사진·음성 원본은 Azure AI Services에서만 인식하고, 모델에는 가린 텍스트만 보낸다. 운영 근거(가용성 테스트, 경고 3개, 관리 ID, Key Vault, Bicep, trace)와 복구 한계는 TRD 6.1절에 있다.

## 측정 결과

배포 앱에서 평가 실행(`POST /api/eval`)으로 합성 사례 5건을 처리한 결과다(2026-11-05 15:37–15:39 KST, 커밋 `a9a4b1ae`, 라이브 5건).

| 지표 | 목표 | 측정값 |
|---|---|---|
| 제도 재현율("확인 필요" 포함, 사례별 평균) | 0.90 이상 | 1.00 |
| 추천 정밀도("규칙상 충족", 사례별 평균) | 0.90 이상 | 1.00 |
| 근거 일치율(모델 인용 근거와 규칙 함수 결과의 일치, 정답 자격 정확도가 아님) | 1.00 | 1.00 |
| 입력부터 승인 대기까지 처리 시간 | 90초 이내 | 평균 40.6초(35.4~49.7초) |
| 가리기 잔존 | 0건 | 0건(재현율 1.00, 오검출 2건) |
| 인식 CER | 사진 0.10 이하, 녹음 0.15 이하 | 사진 0.000, 녹음 0.117 |

문서 작업 시간 절감은 측정값이 아니라 [가정]에서 [계산]한 값이며, 민감도 범위(1건당 15~52분)와 측정하지 않은 항목은 PRD 5.1절·5.2절에 있다. 이전 리비전(`5bb3c20`)의 배포 앱에서는 외부 검토가 사례 4(음성)의 정밀도 0.00을 두 번 재현했다(STT 오인식으로 가구원 수·나이를 놓침). 원인과 `2674bead`의 수정, 수정 뒤 결과는 PRD 5.2절과 `docs/eval-result.md`에 적었다. 확정 이벤트에는 담당자 검토 시간(`review_seconds`)과 고친 구획 수(`edited_sections`)를 기록해 현장 검토 시간을 잴 수 있게 했다.

## 사용 기술

| 영역 | 기술 |
|---|---|
| 서버 | Python 3.12, FastAPI 0.162.0, Uvicorn 0.54.0, Pydantic 2.14.2, python-multipart, httpx |
| 에이전트 | Microsoft Agent Framework(`agent-framework-core` 1.24.0, `agent-framework-github-copilot` 2.1.1), GitHub Copilot SDK 1.0.28(Copilot CLI 런타임 1.0.105), 모델 `claude-sonnet-5.5`(`COPILOT_MODEL`) |
| 사진·음성 인식 | Azure AI Services: Document Intelligence `prebuilt-read`(`azure-ai-documentintelligence`), Speech 빠른 전사 REST API, `azure-identity`(관리 ID) |
| 관측 | OpenTelemetry, `azure-monitor-opentelemetry`, Application Insights |
| 프런트엔드 | 정적 HTML, 바닐라 JavaScript, CSS, Server-Sent Events |
| 배포 | Docker, Azure Container Apps, Azure Container Registry, Azure Key Vault, Azure Developer CLI(`azd`), Bicep |
| 테스트 | pytest(`requirements.txt`에 없으므로 따로 설치, `tests/`는 MAF·네트워크 없이 순수 코어를 검사) |

## 실행·배포

로컬 실행(Python 3.12):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export COPILOT_GITHUB_TOKEN=github_pat_...   # Copilot Requests 권한이 있는 fine-grained PAT
export COPILOT_MODEL=claude-sonnet-5.5
uvicorn app.main:app --port 8000
```

- 브라우저에서 `http://127.0.0.1:8000/`을 연다. `GET /readyz`로 Copilot·AI Services 준비 상태를 확인한다.
- 토큰 없이 `DISABLE_COPILOT=1`로 실행하면 데모 사례 5건은 저장된 실행 재생으로 동작하고, 직접 입력은 409로 거부된다.
- 사진·음성 입력을 쓰려면 `ENABLE_AI_SERVICES=true`와 `AZURE_AI_ENDPOINT`를 정하고, `DefaultAzureCredential`이 쓸 수 있는 자격 증명(예: `az login`)에 해당 리소스의 `Cognitive Services User` 역할이 있어야 한다.
- 단위 테스트: `python -m pytest`(43개, MAF·네트워크 없이 순수 코어 검사). GitHub Actions CI(`.github/workflows/ci.yml`)가 push·PR마다 pytest와 `az bicep build --file infra/main.bicep`을 실행한다. 화면 결함(확정 문서 구획 표시, 확정 후 상태 배지)은 배포 앱 E2E 점검으로 확인한다(TRD 10절).
- 재생 파일 다시 만들기: `python -m scripts.record_replay [case_id ...]`(Copilot 준비 필요, `data/replays/`에 씀).

Azure 배포:

```bash
azd env new dongheng-prod
azd env set COPILOT_GITHUB_TOKEN github_pat_...
azd env set COPILOT_MODEL claude-sonnet-5.5
azd env set ENABLE_AI_SERVICES true
azd env set ALERT_EMAIL team@example.com      # 선택: 비우면 경고만 만들고 메일 작업 그룹은 만들지 않는다
azd up
```

- 지역 기본값은 `koreacentral`이다(`AZURE_LOCATION`, AI Services는 `AZURE_AI_SERVICES_LOCATION`으로 따로 정할 수 있다).
- `azd up`은 리소스 그룹 `rg-<환경 이름>`에 Container Apps, ACR, Key Vault(토큰 보관), Application Insights, AI Services를 만들고, 이미지를 ACR에서 원격 빌드해 배포한다. 현재 배포는 `rg-dongheng-prod`의 Container App `ca-web-7fdjs3dl7icwm`이다.
- 역할 할당 전파 지연으로 첫 배포가 실패하면 `azd up`을 한 번 더 실행한다.

## 사용 데이터

데모 사례와 제도 데이터는 모두 합성·예시 데이터다. 실제 개인정보를 입력하지 않는다.
