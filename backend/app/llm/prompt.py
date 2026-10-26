"""판독 프롬프트와 출력 스키마.

프롬프트를 고칠 때마다 eval 로 20장을 다시 재고 docs/eval_log.md 에 한 줄 남긴다.
"""
from __future__ import annotations

from ..fields import FIELDS

_LABEL_TABLE = "\n".join(f"- {f.schema_key} ({f.key}): {', '.join(f.labels)}" for f in FIELDS)

SYSTEM_PROMPT = f"""너는 한국 행정 문서 판독기다. 사진 속 '주정차 위반 과태료 사전통지서'에서 항목을 읽어 정해진 형식으로만 답한다.

규칙
1. 위치가 아니라 칸 이름(라벨)으로 찾는다. 같은 항목도 기관마다 이름과 위치가 다르다.
{_LABEL_TABLE}
2. 단속 사진 안에 찍힌 시각·장소 표시(장비 오버레이)는 쓰지 않는다. 사진 가장자리나 단속 사진 위에 인쇄된
   시각(TS), 장소, 카메라 번호는 문서의 '위반일시', '위반장소', '증거번호'가 아니다. 본문 표와 문장만 근거로 삼는다.
3. 증거번호는 반드시 '증거번호', '단속번호', '위반번호', '관리번호' 라벨에 직접 연결된 값만 적는다.
   라벨 없이 옆에 보이는 번호, 단속 사진의 번호, 차량번호, 계좌번호는 증거번호로 옮기지 않는다.
   라벨이 없으면 증거번호를 null로 둔다.
4. raw 에는 종이에 적힌 글자를 그대로 옮긴다. value 에는 정규화 값을 적는다:
   날짜 YYYY-MM-DD, 위반일시 YYYY-MM-DD HH:MM(24시간제), 금액은 숫자만, 차량번호는 공백 없이.
5. label_seen 에는 실제로 찾은 칸 이름을 적는다. 표가 아니라 문장에서 찾았으면 "(문장)"이라고 적는다.
6. reduced_fine 은 기한 안에 낼 '감경 후 금액'이다. 깎아 주는 차액(감경액)이나 50% 감경 대상자 예시 금액이 아니다.
7. deadline 은 '의견제출기한', '자진납부 기한' 등으로도 적힌다. 표에 없으면 본문 문장에서 찾는다.
8. account 는 가상계좌가 여러 개면 "은행 번호"를 " | "로 이어 모두 적는다.
9. 찾지 못한 항목은 raw, value, label_seen 을 모두 null 로 둔다. 추측하지 않는다.
10. 주정차 위반 과태료 사전통지서가 아니면 is_parking_prenotice=false.
   흐리거나 잘려서 마감일·금액을 읽을 수 없으면 readable=false, unreadable_reason 에 blur, cut, glare 중 하나.

최종 숫자 확인
- 의견진술기한, 감경과태료, 가상계좌를 출력하기 전에 원문을 한 번 더 확대해 읽는다.
- 가상계좌는 은행별로 숫자를 앞에서부터 끝까지 두 번 대조한다. 숫자 하나라도 확신이 없으면 그 계좌를 추측해 고치지 말고 raw와 value를 null로 둔다.
- 감경과태료는 '기한 내 납부금액' 등 해당 라벨의 금액을 그대로 옮긴다. 원래 과태료, 감경액(차액), 50% 예시 금액을 사용하지 않는다. 쉼표·원 표기를 제거할 때도 숫자 자릿수를 바꾸지 않는다.
- 최종 출력 전 raw의 숫자와 value의 정규화 숫자가 서로 같은 뜻인지 확인한다. 숫자를 임의로 보정하거나 0을 추가하지 않는다.
"""

USER_PROMPT = "이 사진 속 문서를 규칙대로 판독해 기록하라."

POLISH_PROMPT = """너는 고령자를 위한 안내문 편집자다. 받은 문장 목록을 같은 개수, 같은 순서로 더 쉬운 우리말로 다듬는다.
뜻을 바꾸지 말고, 숫자·날짜·금액·계좌번호는 한 글자도 바꾸지 않는다. 한 문장은 짧게, 존댓말(해요체)로 쓴다."""


def extraction_schema() -> dict:
    """Anthropic tool input_schema / OpenAI strict json_schema 에 모두 쓰는 스키마."""
    field = {
        "type": "object",
        "properties": {
            "raw": {"type": ["string", "null"]},
            "value": {"type": ["string", "null"]},
            "label_seen": {"type": ["string", "null"]},
        },
        "required": ["raw", "value", "label_seen"],
        "additionalProperties": False,
    }
    props = {f.schema_key: field for f in FIELDS}
    return {
        "type": "object",
        "properties": {
            "doc_type": {"type": ["string", "null"]},
            "is_parking_prenotice": {"type": "boolean"},
            "readable": {"type": "boolean"},
            "unreadable_reason": {"type": ["string", "null"]},
            "fields": {"type": "object", "properties": props, "required": list(props),
                       "additionalProperties": False},
        },
        "required": ["doc_type", "is_parking_prenotice", "readable", "unreadable_reason", "fields"],
        "additionalProperties": False,
    }


def polish_schema() -> dict:
    return {
        "type": "object",
        "properties": {"sentences": {"type": "array", "items": {"type": "string"}}},
        "required": ["sentences"],
        "additionalProperties": False,
    }
