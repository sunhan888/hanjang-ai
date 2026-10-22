# 한장해결AI 팀 협업 가이드

두 사람이 11월 8일 제출까지 같은 방향으로 일하기 위한 문서입니다. 첫날 1~4장을 함께 읽고 시작하세요.
설계 배경은 [개략 설계서](https://claude.ai/code/artifact/ad16b2e8-b433-44b9-b6c3-2f624e972cd4), 화면 기준은 [모바일 프로토타입](https://claude.ai/artifact/3rZADwBDPJGbC5YBACs9ip)에 있습니다(멘토가 공유해야 열립니다).

---

## 1. 출발점: 이미 되는 것과 남은 것

이 저장소는 멘토가 만든 출발점입니다. API 키 없이도 사진 → 판독 → 결과 화면까지 전 과정이 돌고, 테스트 24개가 통과합니다.
남은 일은 **실제 모델로 정확도를 끌어올리고, 실기기와 배포 환경에서 다듬는 것**입니다.

| 영역 | 지금 상태 | 남은 일 | 담당 |
| --- | --- | --- | --- |
| 판독 (LLM) | mock 판독기로 동작. Claude·OpenAI 연결 코드는 있지만 실제 키로는 아직 미확인 | 실제 키로 1장 확인 → 20장 측정 → 프롬프트 개선 | A |
| 규칙 검증 | 날짜 순서·간격, 연도 보정, 감경 금액, 법정 금액, 형식, 두 번 읽은 값 비교 | 실물 견본에서 나온 실수 반영 | A |
| 근거 (RAG) | 법령 7건, 조문 매핑 + 글자 2-gram TF-IDF 검색 | 국가법령정보센터 원문 대조 후 `verified: true` | A |
| 할 일 (Agent) | 단계 9종 카탈로그, 숫자 대조 가드가 붙은 문장 다듬기(선택 기능) | 사용성 테스트 결과로 문장 수정 | A (B 검토) |
| 화면 | 화면 9개, mock 모드로 모든 상태 확인 가능, 헤드리스 브라우저로 전 과정 확인함 | 실기기 점검, 문구·간격 다듬기 | B |
| 서버·저장소 | FastAPI, 메모리/Supabase 저장소, 결과 24시간 뒤 삭제 | Supabase 연결, HTTPS 배포 | B |
| 평가 | 테스트셋 20장, 일괄 판독·채점 스크립트 | 실물 3장 정답표, 바꿀 때마다 측정 | A |

## 2. 역할과 소유 폴더

소유자는 자기 폴더를 책임지고, 리뷰는 항상 상대가 합니다.

| | A 기획·AI | B 웹·배포 |
| --- | --- | --- |
| 소유 폴더 | `backend/app/llm`, `backend/app/pipeline`, `backend/app/data`, `eval/`, `docs/EVALUATION.md` | `frontend/`, `backend/app/main.py`·`store.py`·`imaging.py`, `supabase/`, `Dockerfile`, `scripts/` |
| 주 산출물 | 프롬프트, 검증 규칙, 법령 데이터, 평가 리포트 | 화면, 서버 연동, 배포 주소, 실기기 점검표 |
| 상대에게 주는 것 | 매일 평가 수치 한 줄, 바뀐 결과 JSON | 배포 주소, 화면 캡처, 실기기에서 판독이 틀린 사진 |

**함께 소유**: `backend/app/schemas.py`와 `docs/API.md`(결과 JSON 계약), 이 문서.

## 3. 일하는 원칙 다섯 가지

1. **계약이 먼저다.** 결과 JSON([API.md](API.md))을 바꾸려면 둘이 합의하고 한 PR에서 같이 바꿉니다.
2. **mock으로 서로 기다리지 않는다.** B는 `?mock`, A는 `eval/run_batch.py`로 각자 끝까지 돌립니다.
3. **숫자는 코드가 책임진다.** LLM이 낸 날짜·금액을 검증 없이 화면에 내보내는 코드는 리뷰에서 막습니다.
4. **작게 자주 합친다.** PR 하나는 하루 안에 리뷰할 크기로, `main`은 언제나 배포 가능한 상태로 둡니다.
5. **수치로 말한다.** 프롬프트·규칙 변경은 평가 리포트의 핵심 수치와 함께 올립니다.

## 4. 첫날 셋업 (10/21, 둘이 함께 1~2시간)

- [ ] GitHub 비공개 저장소를 만들고 이 패키지를 첫 커밋으로 올린다 (`.env` 파일이 없는지 먼저 확인)
- [ ] 둘 다 README의 '5분 실행'으로 로컬에서 사진 한 장 → 결과 화면까지 확인
- [ ] `cd backend && pytest -q` → `24 passed`
- [ ] `python eval/run_batch.py --provider mock-noisy` → `python eval/evaluate.py`를 실행하고 리포트를 같이 읽는다 ([EVALUATION.md](EVALUATION.md) 5장)
- [ ] A: LLM API 키 발급, 사용 금액 한도 설정 / B: Supabase 프로젝트 생성·`supabase/schema.sql` 실행, 배포 서비스 계정
- [ ] 키 관리 규칙 합의: 저장소·메신저에 올리지 않는다. 각자 `backend/.env`에만, 배포 서비스에는 환경변수로 넣는다
- [ ] 6장 일정표를 보고 바꿀 날짜가 있으면 지금 고친다
- [ ] 매일 15분 맞추는 시간을 정한다 (13장)

## 5. Git 규칙

- 브랜치: `main` ← `feat/<담당>-<주제>` (예: `feat/ai-prompt-ts`, `feat/web-heic`)
- 커밋 머리말: `[AI]` `[WEB]` `[API]` `[DOC]` + 무엇을 왜
  - 예: `[AI] 사진 속 시각 무시 규칙을 프롬프트에 예시로 추가 (TS 조용한 오답 4→1)`
- PR: 상대가 리뷰하고 합칩니다. 24시간 넘게 열어 두지 않습니다. 체크리스트는 `.github/pull_request_template.md`가 자동으로 띄웁니다.
- `[API]` PR: 두 사람 모두 승인 + `docs/API.md`·`schemas.py` 수정 + `python backend/scripts/make_mock_results.py` 실행 결과 포함
- 상대 소유 폴더를 고쳐야 하면 먼저 말하고, 그 PR의 리뷰는 소유자가 합니다.

## 6. 13일 일정

★는 둘이 함께 확인하는 마일스톤입니다. 실근무일 기준이며 주말은 비워 두었습니다.

| 날짜 | A 기획·AI | B 웹·배포 | 함께 |
| --- | --- | --- | --- |
| 10/21 (수) | 실제 모델로 notice_06 1장 판독 성공 | Supabase 연결, mock 모드로 첫 배포(HTTPS) | 4장 셋업 |
| 10/22 (목) | 20장 1차 측정 = 기준선, `eval_log.md` 첫 줄 | 실기기 1차: 카메라·앨범·HEIC·업로드 | 측정 결과 공유 |
| 10/23 (금) | 실물 견본 3장 정답표 작성 | 배포본에 실제 모델 연결 | ★ API 계약 v1 동결 |
| 10/26 (월) | 프롬프트 v2: 사진 속 시각(TS)·옆 번호(DN) 대응 | 결과 화면 실데이터 점검 (긴 주소, 계좌 여러 개) | |
| 10/27 (화) | 실물에서 나온 실수로 규칙 보강 + 테스트 | 오류 화면 점검 (흐림·잘림·다른 문서·시간 초과) | |
| 10/28 (수) | 법령 7건 원문 대조, 문장 다듬기 옵션 실험 | 글자 크게·복사·공유·음성 실기기 점검 | |
| 10/29 (목) | 정확도 반복, 처리 시간 측정 | 성능(사진 크기·폴링 간격), 비용 상한 | |
| 10/30 (금) | | | ★ 첫 E2E (9장 체크리스트) |
| 11/2 (월) | 남은 오답 분석 | 사용성 테스트 준비 (11장) | |
| 11/3 (화) | | | ★ 고령자 사용성 테스트 3명 |
| 11/4 (수) | 최종 측정 리포트 | 최종 배포 | ★ 기능 동결 (이후 버그 수정만) |
| 11/5 (목) | 발표 자료 (평가 수치) | 시연 영상 (14장 세 가지 상황) | |
| 11/6 (금) | | | 리허설, 제출물 점검 |
| 11/7~8 | | | 버퍼, ★ 11/8 제출 |

## 7. A (기획·AI) 작업 안내

### 7.1 실제 모델 연결 (10/21)

`backend/.env`에 `LLM_PROVIDER=anthropic`과 `ANTHROPIC_API_KEY`를 넣습니다. OpenAI라면 `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`(이미지 입력과 json_schema 출력을 지원하는 모델)을 넣습니다.

```bash
python eval/run_batch.py --provider anthropic --limit 1   # 1장만
python eval/evaluate.py
```

1장이 오류 없이 돌면 20장 전체를 돌립니다. 20장 한 번에 판독 호출이 20번 나가므로 하루 측정 횟수 상한을 정해 둡니다. 연결이 안 되면 12장을 봅니다.

### 7.2 품질 개선 한 바퀴

1. 리포트의 '조용한 오답 목록'에서 가장 아픈 것 하나를 고른다
2. 원인 가설을 한 줄로 쓴다 (예: "단속 사진의 시각을 본문 대신 읽는다")
3. 프롬프트(`backend/app/llm/prompt.py`)나 규칙(`backend/app/pipeline/validate.py`)을 고친다
4. 20장을 다시 재고 `docs/eval_log.md`에 한 줄 남긴다
5. 조용한 오답이 줄고 과잉 경고가 늘지 않았으면 PR

### 7.3 지금 알려진 약점 (mock-noisy 기준)

- **사진 속 시각(TS)**: 날짜가 그럴듯해서 규칙으로는 못 잡습니다. 프롬프트 규칙 2를 강화하고 실제 모델로 재야 합니다.
- **옆에 찍힌 번호(DN)**: 증거번호 칸에 문서번호가 들어갑니다. 핵심 항목은 아니지만 화면에 나갑니다.
- 연도 오독(YY·XY), 감경액 혼동(RD·50), 문장 속 기한(SD)은 규칙이 '확인 필요'로 잡습니다. 실제 모델이 이 실수를 하는지는 측정해 봐야 압니다.

### 7.4 규칙을 추가할 때

`backend/tests/test_validate.py`에 실패 사례를 먼저 쓰고 → `validate.py`에 규칙 → `pytest -q` → 20장 재측정 순서로 합니다.
맞는 값을 의심하는 규칙(과잉 경고)은 고령자가 화면을 믿지 않게 만듭니다. 과잉 경고 10% 이하를 지킵니다.

### 7.5 실물 견본 3장

`eval/real/`에 이미지와 같은 열 구성의 `ground_truth.csv`를 둡니다. 이 폴더는 `.gitignore`에 들어 있어 커밋되지 않습니다. 이름·주소·계좌를 가린 사본만 씁니다.

```bash
python eval/run_batch.py --provider anthropic --images eval/real --truth eval/real/ground_truth.csv --out eval/real/predictions.csv
python eval/evaluate.py --truth eval/real/ground_truth.csv --pred eval/real/predictions.csv --conditions ""
```

### 7.6 법령 원문 대조

`backend/app/data/laws.json`의 7건을 국가법령정보센터 현행 원문과 대조해 `excerpt`를 고치고 `verified`를 `true`로 바꿉니다. 제16조와 제24조는 지금 발췌·요지라서 특히 확인합니다. 금액표(F6)가 바뀌면 `pipeline/fines.py`도 같이 고칩니다.

## 8. B (웹·배포) 작업 안내

### 8.1 화면은 mock으로

```bash
python -m http.server 5500 --directory frontend
```

→ http://localhost:5500/?mock. 상태별로 `?mock=check`, `today`, `overdue`, `blur`, `cut`, `unsupported`, `error`를 붙입니다.

화면 하나는 `frontend/js/app.js`의 함수 하나입니다: `home`, `guide`, `confirmPhoto`, `readingView`, `resultScreen`, `todoScreen`, `fieldsScreen`, `lawScreen`, `errorView`. 색과 크기는 `css/app.css` 맨 위 변수에 있습니다. '할 일'의 제목과 본문은 서버(`pipeline/agent.py`)가 만들기 때문에 바꾸려면 A와 상의합니다.

### 8.2 실기기 점검표 (iPhone Safari, Android Chrome 각각)

- [ ] '사진 찍기' → 카메라가 바로 열림, '앨범에서 고르기' 동작
- [ ] 아이폰 HEIC 사진 업로드 성공, 세로·가로 사진의 회전이 맞음
- [ ] '가+'가 모든 화면에 적용되고 글자가 겹치지 않음
- [ ] 계좌번호 복사 → 은행 앱에 붙여 넣기 성공
- [ ] '가족에게 보내기' → 휴대폰 공유 창 → 메신저 전송
- [ ] '소리로 듣기' 동작 (무음 모드에서도 확인)
- [ ] 판독 중 화면을 껐다 켜도 결과로 이어짐
- [ ] 결과 링크가 다른 휴대폰에서 열리고, '이 결과 지금 지우기' 뒤에는 열리지 않음
- [ ] 느린 네트워크(개발자 도구 Slow 3G)에서 업로드·판독

### 8.3 Supabase

`supabase/schema.sql`을 SQL Editor에서 실행합니다. Project Settings의 API URL과 service_role 키를 서버 환경변수 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`에 넣습니다. **service_role 키는 프론트와 저장소에 절대 넣지 않습니다.** 만료된 결과의 예약 삭제는 파일 안 주석 한 줄(pg_cron)로 겁니다.

### 8.4 배포

`Dockerfile` 하나로 서버와 화면을 같이 올립니다. 컨테이너를 지원하는 배포 서비스를 팀이 고르고 환경변수(`LLM_PROVIDER`, 키, `SUPABASE_*`)를 넣습니다. `TODAY`는 비워 둡니다. 확인은 `https://<주소>/api/health`로 합니다.
복사·공유 기능은 HTTPS에서만 동작하므로 휴대폰 시험은 배포 주소로 합니다.

### 8.5 브라우저 스모크 테스트

```bash
pip install -r backend/requirements-dev.txt && playwright install chromium
python scripts/smoke_e2e.py --base https://<배포 주소> --mock-states
```

사진 업로드부터 결과·상세 화면까지 자동으로 누르고 `scripts/shots/`에 캡처를 남깁니다. 배포할 때마다 한 번 돌립니다.

## 9. 통합 체크포인트

### ★ 10/23 계약 동결
- [ ] [API.md](API.md) v1을 둘 다 읽었고, 필요한 변경은 반영했다
- [ ] `frontend/mock/*.json`이 지금 서버 출력과 같다 (`python backend/scripts/make_mock_results.py`)

### ★ 10/30 첫 E2E
- [ ] 배포 주소(HTTPS)에서 휴대폰으로 실물 견본을 찍어 결과까지 간다
- [ ] 마감일·낼 돈·계좌가 종이와 같다
- [ ] 일부러 흐리게 찍은 사진 → '다시 찍기' 화면
- [ ] 다른 종류의 고지서 → '아직 읽을 수 없는 문서' 화면
- [ ] 결과 링크가 다른 휴대폰에서 열리고, 지운 뒤에는 열리지 않는다
- [ ] 서버 로그에 판독 값(차량번호·계좌 등)이 남지 않는다
- [ ] 처리 시간 중앙값을 `eval_log.md`에 적었다

### ★ 11/4 기능 동결
- [ ] 평가 리포트: 핵심 3항목 조용한 오답 0건 (테스트셋 20장, 실물 3장)
- [ ] 사용성 테스트에서 나온 수정 목록 처리
- [ ] 법령 7건 `verified`
- [ ] 새 컴퓨터에서 README대로 처음부터 실행됨

## 10. 완료 기준 (모든 PR)

- 테스트 통과, 소유자가 아닌 사람이 리뷰
- AI 변경: 평가 리포트 첨부, 조용한 오답이 늘지 않음
- 화면 변경: 360px 폭에서 가로 스크롤 없음, '가+'에서 겹침 없음, 누르는 곳 44px 이상, 캡처 첨부
- 키·실물 고지서·개인정보가 커밋에 없음

## 11. 고령자 사용성 테스트 (11/3)

- 대상: 부모님 세대 3명, 한 명당 10분. 한 사람은 진행, 한 사람은 기록만 합니다.
- 과제: 실물 견본을 건네며 "이 종이를 보고 언제까지 얼마 내면 되는지 알아봐 주세요." 그 뒤로는 돕지 않습니다.
- 성공 기준: 3명 모두 2분 안에 마감일과 낼 돈을 말한다 (설계서 평가 계획).

| 참가자 | 마감일·금액을 말하기까지 | 막힌 화면 | 도움 요청 횟수 | 오해한 문구 | 고칠 것 |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

## 12. 문제가 생기면

| 증상 | 확인할 것 |
| --- | --- |
| 화면이 하얗다 | 브라우저 콘솔 오류. 글꼴 서버가 막혀도 화면은 떠야 정상(기본 고딕으로 보임) |
| 업로드가 415 BAD_IMAGE | 브라우저가 HEIC를 JPEG로 바꾸지 못한 경우. 카메라로 다시 찍기, 필요하면 서버에 pillow-heif 추가 |
| 판독이 LLM_ERROR | 서버 로그의 예외 이름: 키, 모델명, 사용 한도. 키가 비어 있으면 서버 시작 때 바로 오류 |
| OpenAI 400 (schema) | `OPENAI_MODEL`이 이미지 입력과 json_schema strict를 지원하는지 |
| 결과가 404 | 24시간이 지났거나, 메모리 저장소인데 서버가 재시작됨 → Supabase 연결 |
| 휴대폰에서 복사·공유가 안 됨 | http 주소로 연 경우. 배포(HTTPS) 주소로 시험 |
| D-day가 이상함 | 서버 환경변수 `TODAY`가 남아 있는지. 시연 때만 쓰고 비운다 |

## 13. 매일 15분 맞추기

각자 세 줄씩 말합니다: 어제 한 것 / 오늘 할 것 / 막힌 것.
계약·일정·범위에 영향이 있는 결정은 `docs/decisions.md`에 한 줄로 남깁니다. 다음 날 같은 논의를 반복하지 않기 위해서입니다.

## 14. 시연 준비 (11/5)

- 세 가지 상황을 보여 줍니다: 정상(D-14), 확인 필요(연도 오독을 잡아내는 장면), 기한 지남.
- 실제 모델로 시연하면 날짜에 따라 D-day가 바뀝니다. 시연용 서버에만 `TODAY`를 고정하거나, 상황 2·3은 `?mock=check`, `?mock=overdue`로 보여 줍니다.
- 네트워크가 끊길 때를 대비해 시연 영상을 미리 찍어 둡니다.
- 화면에는 합성 견본과 가린 실물만 씁니다.

## 출처 (설계서와 같음)

- [구리시 과태료 부과 사전처분 안내](https://www.guri.go.kr/www/contents.do?key=7881): 질서위반행위규제법 제16·18·24조, 시행령 제5조·제2조의2 요약
- [금천구 주정차위반 단속 안내](https://www.geumcheon.go.kr/portal/contents.do?key=235), [납부 안내](https://www.geumcheon.go.kr/portal/contents.do?key=236): 금액표, 2시간 가산, 가상계좌 입금 마감 시각
- [수원시 주정차단속 부과 및 절차](https://www.suwon.go.kr/sw-www/deptHome/dep_traffic/traffic02/traffic01_02_05.jsp): 의견 제출 시 감경 불가 안내, 이의제기 60일(제20조)
- 원문 대조 기준: [국가법령정보센터](https://www.law.go.kr)
