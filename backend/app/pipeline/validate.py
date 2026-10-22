"""2단계 규칙 검증 — LLM 이 읽은 값을 코드로 확정하고, 이상하면 '확인 필요'를 붙인다.

규칙을 추가할 때는 backend/tests/test_validate.py 에 실패 사례를 먼저 쓰고,
eval/run_batch.py → eval/evaluate.py 로 '조용한 오답'이 줄었는지 확인한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ..fields import BY_KEY, DOC_TYPE, KEYS
from .fines import expected_amounts
from .normalize import (compact_id, fmt_dt, fmt_won, normalize_plate, parse_accounts, parse_date,
                        parse_datetime, parse_won)

MAX_VIOLATION_TO_ISSUE_DAYS = 60   # 경험값: 단속 뒤 두 달 안에 사전통지가 온다
DEADLINE_GAP_DAYS = (10, 40)       # 하한은 법정(의견 제출 10일 이상), 상한은 경험값
REDUCTION_RATE = 0.8               # 자진납부 20% 감경


@dataclass
class Checked:
    value: object = None        # API 로 나가는 정규화 값
    raw: str | None = None
    label_seen: str | None = None
    llm_value: object = None    # LLM 이 낸 정규화 값 (교차검증용, API 에는 안 나감)
    parsed: object = None       # 내부 계산용 date / datetime / int
    has_time: bool = False
    check: str | None = None
    suggestion: str | None = None

    def flag(self, reason: str, suggestion: str | None = None) -> None:
        if self.check is None:      # 먼저 걸린 (더 구체적인) 사유를 남긴다
            self.check = reason
        if suggestion and self.suggestion is None:
            self.suggestion = suggestion

    def to_api(self) -> dict:
        return {"value": self.value, "raw": self.raw, "label_seen": self.label_seen,
                "check": self.check, "suggestion": self.suggestion}


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _label(key: str, c: Checked) -> str:
    if c.label_seen and not c.label_seen.startswith("("):
        return c.label_seen
    return BY_KEY[key].plain


def _llm_datetime(v) -> datetime | None:
    if not v:
        return None
    s = str(v).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _year_fix(v: datetime, issue: date) -> datetime | None:
    """연도만 잘못 읽었다고 보고, 발행일과 맞는 연도를 찾는다."""
    for y in (issue.year, issue.year - 1):
        try:
            cand = v.replace(year=y)
        except ValueError:
            continue
        if 0 <= (issue - cand.date()).days <= MAX_VIOLATION_TO_ISSUE_DAYS:
            return cand
    return None


def _parse_fields(raw_fields: dict[str, dict]) -> tuple[dict[str, Checked], list[str], list[dict]]:
    f = {k: Checked(raw=_s((raw_fields.get(k) or {}).get("raw")),
                    label_seen=_s((raw_fields.get(k) or {}).get("label_seen")),
                    llm_value=(raw_fields.get(k) or {}).get("value")) for k in KEYS}
    notes: list[str] = []

    # 위반일시
    c = f["위반일시"]
    dt, two, has_time = parse_datetime(c.raw)
    llm_dt = _llm_datetime(c.llm_value)
    if dt is None and llm_dt is not None:
        dt, has_time = llm_dt, len(str(c.llm_value)) > 10
        if c.raw:
            c.flag("글자 모양이 낯설어 날짜를 다시 확인해야 해요.")
    elif dt is not None and llm_dt is not None:
        same = dt == llm_dt if has_time else dt.date() == llm_dt.date()
        if not same:
            c.flag("두 번 읽은 날짜가 서로 달라요.")
    if dt is not None and two:
        notes.append(f"'{_label('위반일시', c)}'의 두 자리 연도를 {dt.year}년으로 읽었어요.")
    c.parsed, c.has_time = dt, has_time
    if dt is not None:
        c.value = dt.strftime("%Y-%m-%d %H:%M") if has_time else dt.date().isoformat()

    # 날짜 두 개
    for key in ("의견진술기한", "발행일"):
        c = f[key]
        d, two = parse_date(c.raw)
        llm_d = _llm_datetime(c.llm_value)
        llm_d = llm_d.date() if llm_d else None
        if d is None and llm_d is not None:
            d = llm_d
            if c.raw:
                c.flag("글자 모양이 낯설어 날짜를 다시 확인해야 해요.")
        elif d is not None and llm_d is not None and d != llm_d:
            c.flag("두 번 읽은 날짜가 서로 달라요.")
        if d is not None and two:
            notes.append(f"'{_label(key, c)}'의 두 자리 연도를 {d.year}년으로 읽었어요.")
        c.parsed = d
        c.value = d.isoformat() if d else None

    # 금액 두 개
    for key in ("과태료금액", "감경과태료"):
        c = f[key]
        n = parse_won(c.raw)
        llm_n = parse_won(c.llm_value)
        if n is None and llm_n is not None:
            n = llm_n
        elif n is not None and llm_n is not None and n != llm_n:
            c.flag("두 번 읽은 금액이 서로 달라요.")
        c.parsed = n
        c.value = n

    # 차량번호
    c = f["위반차량"]
    plate = normalize_plate(c.raw) or normalize_plate(c.llm_value)
    if (c.raw or c.llm_value) and plate is None:
        c.flag("차량번호 모양이 낯설어요.")
    c.value = plate or _s(c.llm_value) or c.raw

    # 가상계좌
    c = f["가상계좌"]
    accounts = parse_accounts(c.raw) or parse_accounts(c.llm_value)
    if (c.raw or c.llm_value) and not accounts:
        c.flag("계좌번호 모양이 낯설어요.")
    c.parsed = accounts
    c.value = " | ".join(f"{a['bank']} {a['number']}".strip() for a in accounts) or None

    # 증거번호 (형식이 기관마다 달라 모양 검사는 하지 않는다)
    c = f["증거번호"]
    c.value = _s(c.raw) or _s(c.llm_value)
    c.parsed = compact_id(c.value)

    # 나머지 글자 항목
    for key in ("발신기관", "위반장소", "위반내용"):
        c = f[key]
        c.value = _s(c.raw) or _s(c.llm_value)
    f["문서종류"].value = DOC_TYPE  # 지원 문서로 분류된 경우에만 여기까지 온다

    return f, notes, accounts


def validate(raw_fields: dict[str, dict], today: date) -> tuple[dict[str, Checked], list[str], dict, list[dict]]:
    """반환: (항목별 Checked, 참고 메모, D-day, 계좌 목록)."""
    f, notes, accounts = _parse_fields(raw_fields)

    # 못 찾은 핵심 항목
    for key in ("의견진술기한", "감경과태료", "가상계좌", "위반일시"):
        if f[key].value in (None, "", []):
            f[key].flag("종이에서 찾지 못했어요.")

    v: datetime | None = f["위반일시"].parsed
    issue: date | None = f["발행일"].parsed
    dl: date | None = f["의견진술기한"].parsed
    vday = v.date() if v else None

    # 날짜 순서와 간격
    if vday and issue:
        if vday > issue:
            fix = _year_fix(v, issue)
            f["위반일시"].flag("안내문을 보낸 날보다 늦은 날짜로 읽혔어요.",
                             fmt_dt(fix, f["위반일시"].has_time) if fix else None)
        elif (issue - vday).days > MAX_VIOLATION_TO_ISSUE_DAYS:
            fix = _year_fix(v, issue)
            gap = (issue - vday).days
            reason = ("안내문을 보낸 날보다 1년 넘게 앞서서 잘못 읽었을 수 있어요." if gap >= 365
                      else f"안내문을 보낸 날보다 {gap}일이나 앞서서 잘못 읽었을 수 있어요.")
            f["위반일시"].flag(reason, fmt_dt(fix, f["위반일시"].has_time) if fix else None)
    if issue and dl:
        gap = (dl - issue).days
        if gap <= 0:
            f["의견진술기한"].flag("안내문을 보낸 날보다 빠른 날짜로 읽혔어요.")
        elif not DEADLINE_GAP_DAYS[0] <= gap <= DEADLINE_GAP_DAYS[1]:
            f["의견진술기한"].flag(f"보낸 날과 마감일 사이가 {gap}일이라 이상해요.")
    if vday and dl and dl <= vday and f["위반일시"].check is None:  # 위반일시가 이미 의심되면 그쪽 탓
        f["의견진술기한"].flag("위반한 날보다 빠른 날짜로 읽혔어요.")

    # 감경 금액
    fine, red = f["과태료금액"].parsed, f["감경과태료"].parsed
    if fine and red:
        expect = round(fine * REDUCTION_RATE)
        if red != expect:
            if red == fine - expect:
                f["감경과태료"].flag("깎아 주는 금액(차액)을 읽은 것 같아요.", fmt_won(expect))
            elif red == fine // 2:
                f["감경과태료"].flag("50% 감경 대상자의 예시 금액을 읽은 것 같아요.", fmt_won(expect))
            else:
                f["감경과태료"].flag("원래 금액의 80%가 아니에요.")
                f["과태료금액"].flag("깎인 금액과 맞지 않아요.")

    # 법정 금액
    if fine:
        category, allowed = expected_amounts(f["위반내용"].value)
        if fine not in allowed:
            f["과태료금액"].flag(f"법에 정한 금액({category})과 달라요.")

    # D-day (서버의 '오늘' 기준. 화면은 이 값을 그대로 쓴다)
    if dl:
        n = (dl - today).days
        state = "upcoming" if n > 0 else "today" if n == 0 else "overdue"
        dday = {"deadline": dl.isoformat(), "days_left": n, "state": state, "today": today.isoformat()}
    else:
        dday = {"deadline": None, "days_left": None, "state": "unknown", "today": today.isoformat()}

    return f, notes, dday, accounts
