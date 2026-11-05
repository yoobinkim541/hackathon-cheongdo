# 동행노트

읍·면 행정복지센터 맞춤형복지팀 담당자가 가정 방문 상담 메모를 붙여 넣으면, 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱이다. 의뢰서는 담당자가 승인해야만 확정된다. 2026 청도 바이브코딩 해커톤 출품작이다.

- 제품 요구사항: [PRD.md](./PRD.md)
- 기술 설계: [TRD.md](./TRD.md)
- 라이브러리 명세 정리: [GitHub Copilot SDK](./docs/reference/copilot-sdk.md), [Microsoft Agent Framework](./docs/reference/agent-framework.md)

## 구성

- Microsoft Agent Framework `WorkflowBuilder`로 가리기 → 사실 구조화 → 분야별 제도 매칭(3개 병렬) → 근거 검증 → 문서 초안 → 승인 요청을 잇는다.
- 모든 에이전트는 `GitHubCopilotAgent`이며, 공유 `CopilotClient` 하나로 GitHub Copilot SDK 세션을 연다.
- 자격 판정은 규칙 함수(도구)가 하고, 모델은 판정 입력값 추출, 검사 우선순위 판단, 추가 질문 작성, 문서 초안에만 쓴다.
- Azure Container Apps, Container Registry, Key Vault, Application Insights에 `azd up`으로 배포한다.

## 사용 데이터

데모 사례와 제도 데이터는 모두 합성·예시 데이터다. 실제 개인정보를 입력하지 않는다.
