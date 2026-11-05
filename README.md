# 청도 바이브코딩 해커톤 — 팀 저장소

[청도 바이브코딩 해커톤](https://github.com/hackersground-kr/hackathon-cheongdo) 출품작 저장소입니다.

> 심사는 AI 에이전트가 **`PRD.md`, `TRD.md`, 실제 배포된 앱**을 보고 진행합니다. README는 보조 자료입니다.

## 대회 핵심 요약

| 항목 | 내용 |
|---|---|
| 일시 / 장소 | 2026-11-05(목) 09:00~18:00 / 청도신화랑풍류마을 |
| 팀 | 리더 포함 1~4인 |
| 결과물 | **웹 앱** + **Azure 배포** (언어 자유) |
| AI 도구 | VS Code + GitHub Copilot, Copilot CLI, Copilot app만 허용 (**타사 AI 코딩 도구 금지**) |
| 필수 기술 | **GitHub Copilot SDK + Microsoft Agent Framework** |
| **최종 제출 마감** | **11-05 16:30 KST** (1차 제출 15:00, 팀당 최대 2회, 마지막 제출 기준) |

### 시간표
| 시각 | 내용 |
|---|---|
| 09:00 | 등록·체크인 |
| 10:00 | 개회·주제 공개 |
| 11:00 | 아이디어·팀 빌딩·환경 세팅 |
| 13:00 | 집중 개발 Ⅰ |
| 15:00 | 1차 제출·자동 검수 |
| 15:20 | 집중 개발 Ⅱ |
| **16:30** | **최종 제출 마감** |
| 17:00 | 시상식 |

### 평가 기준
| # | 항목 | 가중치 |
|---|---|---:|
| 1 | Copilot SDK·Agent Framework 효과적 활용 (모델 연결, 에이전트 설계, 오케스트레이션, 도구 호출, 컨텍스트, 스트리밍) | 25% |
| 2 | 생산성 향상 효과·문제 적합성 | 18% |
| 3 | Azure 클라우드 통합 (실배포, 반복 배포, 관찰 가능성. 불필요한 서비스 남발은 감점) | 18% |
| 4 | 기능 완성도·기술 구현 (E2E 동작, 오류 처리, 반응형) | 16% |
| 5 | UX·워크플로 (지연·오류 처리, 투명성, 접근성, 사용자 통제권) | 12% |
| 6 | 책임 있는 AI·보안 (AI 결과 표시, 위험 작업 확인, 프롬프트 인젝션, 비밀 관리) | 6% |
| 7 | 혁신성·독창성 | 5% |

### 제출 체크리스트
- [ ] 팀원 전원 [GitHub 핸들 등록](https://github.com/hackersground-kr/hackathon-cheongdo/issues/new?template=01-github-handle.yml) (`@` 없이)
- [ ] 팀 리더가 [팀 등록](https://github.com/hackersground-kr/hackathon-cheongdo/issues/new?template=02-team-building.yml)
- [ ] 저장소가 팀 리더 계정의 **공개 저장소**
- [ ] 루트에 `PRD.md`, `TRD.md` 작성 완료
- [ ] Azure **기본 도메인**(`*.azurecontainerapps.io`, `*.azurewebsites.net` 등)으로 배포. 커스텀 도메인 불가
- [ ] **로그인 없이** 핵심 기능 사용 가능. 막혀 있으면 전 항목 최저점
- [ ] [결과 제출](https://github.com/hackersground-kr/hackathon-cheongdo/issues/new?template=03-result-submission.yml): 커밋 해시 + 배포 URL (토큰·비밀번호 절대 입력 금지)
- [ ] 제출 이슈의 댓글과 `complete` / `invalid` 라벨 확인
- [ ] 비용 정산용 Copilot·Azure **사용량 캡처**(11-05 17:00 ~ 11-06 12:00)와 **결제 영수증**(12-01 ~ 12-05) 보관

## 청도 사회문제 (아이디어 후보)

| 분야 | 주제 |
|---|---|
| 경제 | 소상공인 매출 증대, 전통시장·상권 활성화, 창업·일자리 확대 |
| 농업 | 농산물 유통 경쟁력, 수급·가격 예측, 병해충 조기 경보, 초보 농부 도우미, 일손 부족, 귀농·귀촌 정착 |
| 복지 | 독거노인·고독사·디지털 소외, 장애인 이동권·정보 격차, 저소득층, 아동·청소년 돌봄, 1인 가구, 복지 사각지대 |
| 청년 | 맞춤형 청년 혜택, 고립·은둔 청년·마음 건강, 취업·창업·정착 |
| 안전 | 어린이·노인·야간 보행 안전, 재난·재해, 노후 시설물·도로 파손, 주민 참여 안전 |
| 관광 | 문화관광 통합 플랫폼, 관광 자원 활성화, 맛집 발굴·홍보, 생활인구 유입 |
| 기타 | 군민 소통, 행정 AI 개인정보 보호, 대중교통, 오지 생필품 구입, 생활체육 |

원문: [cheongdo-social-issues.md](https://github.com/hackersground-kr/hackathon-cheongdo/blob/main/references/cheongdo-social-issues.md)

## 보일러플레이트 구조

```
app/
  agent.py        # Microsoft Agent Framework GitHubCopilotAgent + @tool 함수 (주제에 맞게 수정)
  main.py         # FastAPI: /api/health, /api/chat (SSE 스트리밍), 정적 파일
  static/index.html  # 반응형 채팅 UI (AI 생성 표시, 스트리밍 출력)
PRD.md / TRD.md   # 심사 필수 문서 템플릿
Dockerfile        # Azure Container Apps 배포용
```

## 로컬 실행

Copilot 라이선스가 있는 GitHub 계정의 토큰이 필요합니다. Copilot CLI는 SDK가 처음 실행될 때 자동으로 내려받습니다.

```bash
python -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env   # GITHUB_TOKEN 입력
```

```bash
set -a && source .env && set +a && uvicorn app.main:app --reload
```

http://localhost:8000 접속

## Azure 배포 (Container Apps)

```bash
az login
```

```bash
az containerapp up -n cheongdo-app -g cheongdo-rg -l koreacentral --source . --ingress external --target-port 8000
```

```bash
az containerapp secret set -n cheongdo-app -g cheongdo-rg --secrets github-token=<토큰>
```

```bash
az containerapp update -n cheongdo-app -g cheongdo-rg --set-env-vars GITHUB_TOKEN=secretref:github-token
```

출력된 `https://<앱>.<region>.azurecontainerapps.io` URL을 결과 제출에 사용합니다.
