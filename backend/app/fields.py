"""판독 항목 정의 — 정답표(eval/testset/ground_truth.csv), API, 프롬프트가 모두 이 표를 따른다.

항목을 바꾸면 docs/API.md 와 frontend 의 FIELD_VIEW 도 함께 바꾼다.
"""
from __future__ import annotations

from typing import NamedTuple


class FieldDef(NamedTuple):
    key: str            # 한국어 키 (API·정답표 열 이름)
    schema_key: str     # LLM 출력 스키마 키 (영문: 모든 LLM API 에서 안전)
    plain: str          # 화면에 쓰는 쉬운 이름
    labels: tuple       # 종이에 적히는 라벨 동의어 (프롬프트에 그대로 들어감)


FIELDS: tuple[FieldDef, ...] = (
    FieldDef("문서종류", "doc_title", "문서 종류", ("제목",)),
    FieldDef("발신기관", "issuer", "보낸 곳", ("서명란의 기관장 명의",)),
    FieldDef("증거번호", "evidence_no", "단속번호", ("증거번호", "단속번호", "위반번호", "관리번호")),
    FieldDef("위반차량", "plate", "어떤 차", ("위반차량", "차량번호", "자동차등록번호", "위반차량번호")),
    FieldDef("위반일시", "violated_at", "언제", ("위반일시", "단속일시", "적발일시", "위반 일시")),
    FieldDef("위반장소", "place", "어디서", ("위반장소", "단속장소", "적발장소", "위반 장소")),
    FieldDef("위반내용", "violation", "무슨 위반", ("위반내용", "위반사항", "위반행위", "위반법규")),
    FieldDef("과태료금액", "fine", "원래 금액", ("과태료 금액", "부과금액", "과태료", "부과예정 과태료")),
    FieldDef("감경과태료", "reduced_fine", "기한 안에 낼 금액",
             ("감경 과태료", "자진납부 금액", "감경 시 납부금액", "기한 내 납부금액", "감경 후 납부금액")),
    FieldDef("의견진술기한", "deadline", "마감일", ("의견진술기한", "의견제출기한", "의견제출 기한", "자진납부 기한")),
    FieldDef("가상계좌", "account", "입금 계좌", ("가상계좌", "납부계좌", "입금전용계좌", "전용계좌")),
    FieldDef("발행일", "issued_on", "보낸 날", ("발행일", "발송일", "통지일", "라벨 없이 서명 위 날짜")),
)

KEYS = tuple(f.key for f in FIELDS)
BY_KEY = {f.key: f for f in FIELDS}

# 틀리면 사용자가 손해를 보는 핵심 3항목 (평가의 '과업 성공' 기준)
CORE = ("의견진술기한", "감경과태료", "가상계좌")
# 이 항목에 문제가 있으면 '낼 돈·마감일'이 흔들린다
AFFECTS_PAYMENT = frozenset({"의견진술기한", "감경과태료", "과태료금액", "가상계좌"})
# '확인 필요'를 보여 줄 우선순위
CHECK_ORDER = ("의견진술기한", "감경과태료", "가상계좌", "과태료금액", "위반일시", "발행일",
               "위반차량", "위반장소", "위반내용", "증거번호", "발신기관", "문서종류")

DOC_TYPE = "주정차위반 과태료 사전통지서"
