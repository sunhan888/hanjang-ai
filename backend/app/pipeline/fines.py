"""주정차 위반 과태료 법정 금액 (도로교통법 시행령 별표 6 기준, 승용/승합).

출처: 금천구 주정차위반 단속·납부 안내 (docs/GUIDE.md 출처 목록).
같은 장소에서 2시간 이상 위반하면 1만원이 더해진다.
금액표가 바뀌면 여기와 backend/app/data/laws.json 의 F6 을 함께 고친다.
"""
from __future__ import annotations

TWO_HOUR_EXTRA = 10_000

# (이름, 위반내용에서 찾을 낱말, (승용, 승합))
CATEGORIES = (
    ("어린이보호구역", ("어린이", "스쿨존"), (120_000, 130_000)),
    ("소방시설 주변", ("소방", "소화전"), (80_000, 90_000)),
)
GENERAL = ("일반 주정차 위반", (40_000, 50_000))


def _with_extra(base: tuple[int, ...]) -> set[int]:
    return set(base) | {b + TWO_HOUR_EXTRA for b in base}


ALL_AMOUNTS = _with_extra(GENERAL[1]).union(*(_with_extra(c[2]) for c in CATEGORIES))


def expected_amounts(violation_text: str | None) -> tuple[str, set[int]]:
    """위반내용 문구로 허용 금액 집합을 고른다. 모르면 알려진 금액 전체."""
    text = violation_text or ""
    for name, words, base in CATEGORIES:
        if any(w in text for w in words):
            return name, _with_extra(base)
    if any(w in text for w in ("주정차", "주·정차", "주차", "정차")):
        return GENERAL[0], _with_extra(GENERAL[1])
    return "주정차 위반", set(ALL_AMOUNTS)
