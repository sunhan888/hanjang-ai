# API 계약 v1

프론트(B)와 AI(A)가 함께 지키는 약속입니다. 바꾸려면 [GUIDE](GUIDE.md) 5장의 `[API]` 절차를 따릅니다.
코드 기준은 `backend/app/schemas.py`이고, 실제 출력 예시는 `frontend/mock/result.json`·`result-check.json`·`result-today.json`·`result-overdue.json`입니다.

## 엔드포인트

| 메서드·경로 | 요청 | 성공 응답 | 실패 응답 |
| --- | --- | --- | --- |
| `POST /api/analyses` | multipart, 필드 이름 `image` (JPEG 권장, 10MB 이하) | `202 {id, status: "processing", stage: "reading"}` | `400 EMPTY`, `413 TOO_LARGE`, `415 BAD_IMAGE` |
| `GET /api/analyses/{id}` | | `200 Analysis` | `404 NOT_FOUND` (없음·만료·삭제) |
| `DELETE /api/analyses/{id}` | | `204` | |
| `GET /api/health` | | `200 {ok, provider, store, today}` | |

HTTP 오류 본문은 `{"detail": {"code": "BAD_IMAGE", "message": "사용자에게 보여도 되는 문장"}}` 모양입니다.
판독은 백그라운드에서 돌기 때문에, 판독 자체의 실패는 HTTP 오류가 아니라 `Analysis.status = "failed"`로 알려 줍니다.

## Analysis

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | string (uuid) | |
| `status` | `processing` · `done` · `failed` | |
| `stage` | `reading` · `checking` · `planning` · `done` | 판독 중 화면의 세 단계 |
| `result` | Result 또는 null | `status = done`일 때 |
| `error_code` | `UNREADABLE` · `UNSUPPORTED` · `LLM_ERROR` | `status = failed`일 때 |
| `error_reason` | `blur` · `cut` · `glare` | `UNREADABLE`일 때 다시 찍기 안내를 고른다 |
| `error_message` | string | 사용자에게 보여도 되는 문장 |
| `created_at`, `expires_at` | ISO 8601 | 결과는 24시간 뒤 사라진다 |

프론트에서만 쓰는 오류 코드: `NETWORK`(연결 실패), `TIMEOUT`(90초 넘게 processing).

## Result

| 필드 | 설명 |
| --- | --- |
| `version` | `"1"` |
| `doc_type` | `"주정차위반 과태료 사전통지서"` |
| `issuer` | 보낸 곳 (예: `서울특별시 마포구청장`) |
| `fields` | 판독 항목 12개 (아래) |
| `accounts` | `[{bank, number}]` 가상계좌 목록 |
| `dday` | `{deadline, days_left, state, today}`. `state`는 `upcoming` · `today` · `overdue` · `unknown`. 서버의 '오늘' 기준으로 계산하며 화면은 이 값을 그대로 쓴다 |
| `summary` | '소리로 듣기'와 '가족에게 보내기'에 쓰는 요약 문장 |
| `steps` | 할 일 `[{type, title, body, cites}]`. 화면은 받은 순서대로 보여 준다 |
| `citations` | 근거 법령 `[{id, law, article, title, excerpt, plain, source_url, verified}]` |
| `notes` | 참고 메모 (예: 두 자리 연도를 2026년으로 읽었음) |

### fields: 항목마다 같은 모양

`{value, raw, label_seen, check, suggestion}`

- `value`: 정규화 값 (형식은 아래 표)
- `raw`: 종이에 적힌 그대로
- `label_seen`: 종이에서 찾은 칸 이름. `"(문장)"`은 본문 문장에서 찾음, `"(제목)"`, `"(서명란)"`, `null`은 못 찾음
- `check`: '확인 필요' 사유. `null`이면 검증 통과
- `suggestion`: 검증이 제안하는 값(화면에 그대로 보여 주는 문장). 예: `"2026년 9월 24일(목) 오전 11시 14분"`

| 키 | value 형식 |
| --- | --- |
| `문서종류` | 고정 문자열 |
| `발신기관`, `증거번호`, `위반장소`, `위반내용` | 문자열 |
| `위반차량` | 공백 없는 차량번호 (`18노6336`) |
| `위반일시` | `YYYY-MM-DD HH:MM` (시각을 못 읽으면 `YYYY-MM-DD`) |
| `과태료금액`, `감경과태료` | 정수(원). 감경과태료는 기한 안에 낼 '감경 후' 금액 |
| `의견진술기한`, `발행일` | `YYYY-MM-DD` |
| `가상계좌` | `은행 번호 \| 은행 번호` |

### steps.type (Agent 단계 카탈로그)

| type | 나오는 때 | cites |
| --- | --- | --- |
| `CHECK` | '확인 필요' 항목이 있을 때 맨 앞 (결과 화면은 노란 카드로 보여 줌) | |
| `VERIFY` | 기한 전·당일·모름 | |
| `PAY` | 기한 전·당일·모름 | `L18`, `L18-5` |
| `OBJECT` | 기한 전·당일·모름 | `L16` |
| `REDUCE50` | 기한 전·당일·모름 | `L2-2` |
| `OVERDUE` | 기한 지남 | `L24` |
| `CALL` | 기한 지남 | |
| `OBJECT_LATE` | 기한 지남 | `L20` |
| `SCAM` | 항상 마지막 | |

금액표 `F6`은 `citations`에 항상 붙습니다. 카탈로그 밖의 단계는 만들지 않습니다(새 단계가 필요하면 계약 변경).

## 계약을 바꾸는 순서

1. 변경 이유와 모양을 둘이 합의한다
2. `schemas.py` → 서버 코드 → 이 문서 순서로 고친다
3. `python backend/scripts/make_mock_results.py`로 `frontend/mock/*.json`을 다시 만든다
4. 프론트를 고친다
5. `[API]` PR을 올리고 두 사람 모두 승인한다. 화면이 깨지는 변경이면 `version`을 올린다
