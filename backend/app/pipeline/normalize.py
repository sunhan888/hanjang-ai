"""종이에 적힌 글자(raw)를 비교 가능한 값으로 바꾼다.

원칙: 숫자는 코드가 책임진다. LLM 이 낸 정규화 값(value)은 '두 번째 의견'으로만 쓰고,
여기서 raw 를 직접 파싱한 값과 다르면 검증 단계에서 '확인 필요'를 붙인다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time

WEEKDAYS = "월화수목금토일"

_Y_SEP = r"\s*(?:[.\-/]|년)\s*"
_M_SEP = r"\s*(?:[.\-/]|월)\s*"
_DATE4 = re.compile(rf"(?P<y>\d{{4}}){_Y_SEP}(?P<m>\d{{1,2}}){_M_SEP}(?P<d>\d{{1,2}})")
_DATE2 = re.compile(rf"(?<!\d)(?P<y>\d{{2}}){_Y_SEP}(?P<m>\d{{1,2}}){_M_SEP}(?P<d>\d{{1,2}})(?!\d)")
_TIME = re.compile(r"(?P<ap>오전|오후|AM|PM|am|pm)?\s*(?P<h>\d{1,2})\s*(?::|시)\s*(?P<mi>\d{1,2})")
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
_PLATE = re.compile(r"(?<!\d)(\d{2,3})\s*([가-힣])\s*(\d{4})(?!\d)")
_ACCOUNT_NUM = re.compile(r"\d[\d\-\s]{8,}\d")

# 긴 이름을 먼저 (IBK기업은행 이 기업은행 보다 먼저 잡히도록)
BANKS = ("IBK기업은행", "KB국민은행", "NH농협은행", "BNK경남은행", "BNK부산은행", "DGB대구은행", "SC제일은행",
         "기업은행", "국민은행", "농협은행", "신한은행", "우리은행", "하나은행", "경남은행", "부산은행", "대구은행",
         "광주은행", "전북은행", "제주은행", "씨티은행", "수협은행", "우체국", "새마을금고", "신협", "농협", "수협",
         "케이뱅크", "카카오뱅크", "토스뱅크")


def find_date(text) -> tuple[date | None, bool, int]:
    """(날짜, 연도가 두 자리였는지, 날짜가 끝난 위치)."""
    if not text:
        return None, False, 0
    s = str(text)
    m = _DATE4.search(s)
    two_digit = False
    if not m:
        m = _DATE2.search(s)
        two_digit = m is not None
    if not m:
        return None, False, 0
    y = int(m.group("y"))
    if y < 100:
        y += 2000
    try:
        return date(y, int(m.group("m")), int(m.group("d"))), two_digit, m.end()
    except ValueError:
        return None, two_digit, m.end()


def parse_date(text) -> tuple[date | None, bool]:
    d, two, _ = find_date(text)
    return d, two


def parse_time(text) -> time | None:
    if not text:
        return None
    m = _TIME.search(str(text))
    if not m:
        return None
    h, mi = int(m.group("h")), int(m.group("mi"))
    ap = (m.group("ap") or "").lower()
    if ap in ("오후", "pm") and h < 12:
        h += 12
    if ap in ("오전", "am") and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    return time(h, mi)


def parse_datetime(text) -> tuple[datetime | None, bool, bool]:
    """(일시, 연도 두 자리 여부, 시각을 찾았는지)."""
    d, two, end = find_date(text)
    if d is None:
        return None, two, False
    t = parse_time(str(text)[end:])
    return datetime.combine(d, t or time(0, 0)), two, t is not None


def parse_won(text) -> int | None:
    """'금 40,000원', '₩40,000', '40000원', '96,000원 (20% 감경)', '12만원' → 정수."""
    if text is None or isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text).replace(" ", "")
    if "만" in s and not re.search(r"\d,\d{3}", s):
        m = re.search(r"(\d+)만(?:(\d+)천)?", s)
        if m:
            return int(m.group(1)) * 10000 + int(m.group(2) or 0) * 1000
    m = _NUM.search(s)
    return int(m.group().replace(",", "")) if m else None


def normalize_plate(text) -> str | None:
    """'18노 6336 (승용)' → '18노6336'."""
    if not text:
        return None
    m = _PLATE.search(str(text))
    return f"{m.group(1)}{m.group(2)}{m.group(3)}" if m else None


def parse_accounts(text) -> list[dict]:
    """'우리은행 7897-667-528856 | 신한은행 …' → [{bank, number, digits}, …]."""
    if not text:
        return []
    out: list[dict] = []
    for part in re.split(r"[|\n;,]+", str(text)):
        part = part.strip()
        if not part:
            continue
        m = _ACCOUNT_NUM.search(part)
        if not m:
            continue
        number = re.sub(r"\s+", "", m.group())
        digits = re.sub(r"\D", "", number)
        if not 10 <= len(digits) <= 16:
            continue
        bank = next((b for b in BANKS if b in part), "")
        out.append({"bank": bank, "number": number, "digits": digits})
    return out


def compact_id(text) -> str | None:
    """증거번호 비교용: 공백·하이픈 제거."""
    return re.sub(r"[\s\-]", "", str(text)) if text else None


# ---- 화면 문장용 표기 ----

def fmt_won(n: int | None) -> str:
    return "" if n is None else f"{n:,}원"


def fmt_md(d: date) -> str:
    return f"{d.month}월 {d.day}일({WEEKDAYS[d.weekday()]})"


def fmt_ymd(d: date) -> str:
    return f"{d.year}년 {fmt_md(d)}"


def fmt_dt(dt: datetime, with_time: bool = True) -> str:
    if not with_time:
        return fmt_ymd(dt.date())
    ap = "오전" if dt.hour < 12 else "오후"
    h = dt.hour % 12 or 12
    return f"{fmt_ymd(dt.date())} {ap} {h}시 {dt.minute}분"
