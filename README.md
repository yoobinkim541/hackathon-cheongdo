# 동행노트

읍·면 행정복지센터 맞춤형복지팀 담당자가 가정 방문 상담 메모를 입력하거나 손글씨 메모 사진·상담 녹음을 올리면, 이를 텍스트로 바꾸고 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱이다. 의뢰서는 담당자가 승인해야만 확정된다. 2026 청도 바이브코딩 해커톤 출품작이다.

- 제품 요구사항: [PRD.md](./PRD.md)
- 기술 설계: [TRD.md](./TRD.md)
- 구현 명세 요약: [SPEC.md](./SPEC.md)
- UI 시안: [Figma — 청도 해커톤 UI 시안](https://www.figma.com/design/1jSoQXwAjX8pv01kjulZYf/%EC%B2%AD%EB%8F%84-%ED%95%B4%EC%BB%A4%ED%86%A4-UI-%EC%8B%9C%EC%95%88?node-id=0-1)
- 라이브러리 명세 정리: [GitHub Copilot SDK](./docs/reference/copilot-sdk.md), [Microsoft Agent Framework](./docs/reference/agent-framework.md)

## 구성

- Microsoft Agent Framework `WorkflowBuilder`로 입력 분기(텍스트·사진·음성) → 인식(OCR·STT) → 가리기 → 인식 결과 정리 → 사실 구조화 → 분야별 제도 매칭(3개 병렬) → 근거 검증 → 문서 초안 → 승인 요청을 잇는다.
- 모든 에이전트(6개)는 `GitHubCopilotAgent`이며, 공유 `CopilotClient` 하나로 GitHub Copilot SDK 세션을 연다.
- 자격 판정은 규칙 함수(도구)가 하고, 모델은 인식 결과 정리, 판정 입력값 추출, 검사 우선순위 판단, 추가 질문 작성, 문서 초안에만 쓴다.
- Azure Container Apps, Container Registry, Key Vault, Application Insights, Azure AI Services(Document Intelligence·Speech)에 `azd up`으로 배포한다. 사진·음성 원본은 Azure AI Services에서만 인식하고, 모델에는 가린 텍스트만 보낸다.

## 심사 기준별 구현 위치

| 심사 항목 | 구현 | 근거 문서 |
|---|---|---|
| Copilot SDK·Agent Framework 활용 | `GitHubCopilotAgent` 6개와 공유 `CopilotClient`, `WorkflowBuilder`의 switch-case·fan-out/fan-in·`request_info`, 함수 도구, `AgentSession`, 컨텍스트 공급자, 미들웨어, SSE 스트리밍 | TRD 2·3절 |
| 생산성·문제 적합성 | 방문 상담 후 문서 작업(메모 정리, 제도 대조, 의뢰서 작성) 단축. 처리 시간·재현율은 평가 실행으로 측정 | PRD 2·5절 |
| Azure 통합 | Container Apps, ACR, Key Vault, Application Insights, AI Services, 관리 ID, `azd up` + Bicep | TRD 6절 |
| 기능 완성도 | 데모 사례 5건 전체 흐름, 승인·거부 경로, 평가 실행, 반응형 UI | PRD 4절, TRD 7·9절 |
| UX·워크플로 | 단계 타임라인, 근거 패널, 구획별 수정·되돌리기, 접근성 | TRD 9절 |
| 책임 있는 AI·보안 | 가리기, AI 초안 표시, 승인 후 확정, 인젝션 방어, Key Vault | PRD 7절, TRD 8절 |
| 혁신성 | 규칙 판정 + 근거 대조 검증, 사진·음성 메모 입력 | PRD 8절 |

## 사용 데이터

데모 사례와 제도 데이터는 모두 합성·예시 데이터다. 실제 개인정보를 입력하지 않는다.
