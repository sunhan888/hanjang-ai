# 한장해결AI

고령자가 **주정차위반 과태료 사전통지서**를 사진 한 장으로 올리면, 마감일·낼 돈·할 일을 쉬운 말로 알려 주는 모바일 웹입니다.
코디세이 AI 네이티브 과정 Final Project (A2팀, 제출 2026-11-08).

> 처음이면 **[docs/GUIDE.md](docs/GUIDE.md)** (팀 협업 가이드)부터 읽으세요.

| 문서 | 내용 |
| --- | --- |
| [docs/GUIDE.md](docs/GUIDE.md) | 역할, Git 규칙, 13일 일정, 담당별 작업 안내, 체크포인트 |
| [docs/API.md](docs/API.md) | 결과 JSON 계약 (프론트와 AI가 함께 지키는 약속) |
| [docs/EVALUATION.md](docs/EVALUATION.md) | 정확도 측정 방법과 지표 |
| [docs/sample_eval_report.md](docs/sample_eval_report.md) | mock-noisy로 돌린 평가 리포트 예시 |
| 설계서·프로토타입 | 멘토가 공유한 링크: [개략 설계서](https://claude.ai/code/artifact/ad16b2e8-b433-44b9-b6c3-2f624e972cd4), [모바일 프로토타입](https://claude.ai/artifact/3rZADwBDPJGbC5YBACs9ip) |

## 처리 흐름

```
휴대폰: 사진을 1600px JPEG로 줄임 ─▶ POST /api/analyses ─▶ 202 {id}
서버(백그라운드): ① 판독(LLM, 칸 이름으로 찾기) ─▶ ② 규칙 검증(코드) ─▶ ③ 근거(법령 RAG) ─▶ ④ 할 일(Agent)
휴대폰: GET /api/analyses/{id} 를 1.5초마다 ─▶ 결과 화면 (결과는 24시간 뒤 삭제, 사진은 저장하지 않음)
```

## 구성

```
hanjang-ai/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            API 서버 (+ frontend 정적 파일 제공)
│  │  ├─ schemas.py         결과 JSON 계약
│  │  ├─ fields.py          판독 항목 12개 정의
│  │  ├─ llm/               판독기: mock, Claude, OpenAI + 프롬프트
│  │  ├─ pipeline/          ① 판독 → ② 검증 → ③ 근거 → ④ 할 일
│  │  ├─ data/laws.json     근거 법령 7건
│  │  └─ store.py           결과 저장소 (메모리 / Supabase)
│  ├─ tests/                pytest 24개
│  └─ scripts/make_mock_results.py   frontend/mock/*.json 다시 만들기
├─ frontend/                바닐라 HTML·CSS·JS, 화면 9개, mock/ (서버 없이 보기)
├─ eval/                    테스트셋 20장, 일괄 판독(run_batch), 채점(evaluate), 생성기
├─ supabase/schema.sql      결과 표 + (선택) 법령 표
├─ scripts/smoke_e2e.py     브라우저 스모크 테스트
├─ docs/                    가이드·계약·평가·기록
└─ Dockerfile               서버 + 화면 한 컨테이너
```

## 5분 실행 (API 키 없이)

Python 3.11 이상.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env            # Windows: copy ..\.env.example .env
uvicorn app.main:app --reload --port 8000
```

브라우저에서 http://localhost:8000 을 열고 '앨범에서 고르기'로 아무 사진이나 올리면, 예시(테스트셋 notice_06) 결과가 나옵니다. 기본 판독기가 `LLM_PROVIDER=mock`이기 때문입니다.

- **휴대폰으로 보기**: 같은 와이파이에서 `uvicorn app.main:app --host 0.0.0.0 --port 8000`을 켜고 `http://<PC의 IP>:8000`을 엽니다. 복사·공유는 HTTPS에서만 동작하니 배포 주소로 시험하세요.
- **화면만 보기 (서버 없이)**: `python -m http.server 5500 --directory frontend` → http://localhost:5500/?mock
  상태별로 `?mock=check | today | overdue | blur | cut | unsupported | error`를 붙입니다.

## 실제 모델 연결

`backend/.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
```

OpenAI라면 `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`(이미지 입력과 json_schema 출력을 지원하는 모델)을 넣습니다.
처음에는 한 장으로 확인합니다: `python eval/run_batch.py --provider anthropic --limit 1`

## 테스트와 평가

```bash
cd backend && pytest -q                                   # 단위·API 테스트 (24개)
cd .. && python eval/run_batch.py --provider mock-noisy   # 테스트셋 20장 일괄 판독 → eval/predictions.csv
python eval/evaluate.py --out eval/report.md              # 채점 리포트
```

## 배포

`Dockerfile` 하나로 서버와 화면을 같이 올립니다. 환경변수는 `.env.example`을 참고하고, 확인은 `/api/health`로 합니다. 자세한 순서는 [GUIDE 8.4](docs/GUIDE.md#84-배포)에 있습니다.

## 출처·기여 표기

이 저장소의 첫 버전은 멘토가 제공한 출발점이며, 팀이 수정·확장합니다. 과정 규정상 외부 도움을 밝혀야 하면 이 문단을 유지하세요.
`backend/app/data/laws.json`의 법령 문구는 국가법령정보센터 원문과 대조하기 전입니다(GUIDE 7.6). 이 서비스는 안내 서비스이며 법률 자문이 아닙니다.
