from datetime import date, datetime

from app.pipeline.normalize import (normalize_plate, parse_accounts, parse_date, parse_datetime, parse_won)


def test_date_formats():
    for raw in ("2026.11.03", "2026. 11. 3.", "2026-11-03", "2026년 11월 3일(화)", "2026.11.03(화) 까지"):
        assert parse_date(raw) == (date(2026, 11, 3), False), raw


def test_two_digit_year_is_marked():
    assert parse_date("26. 11. 3.") == (date(2026, 11, 3), True)
    assert parse_date("26.11.03") == (date(2026, 11, 3), True)


def test_datetime_formats():
    cases = {
        "2026.09.24(목) 11:14": datetime(2026, 9, 24, 11, 14),
        "2026년 9월 14일 14시 32분": datetime(2026, 9, 14, 14, 32),
        "2026.09.14 오후 02:32": datetime(2026, 9, 14, 14, 32),
        "2026.09.14 오전 12:05": datetime(2026, 9, 14, 0, 5),
        "2026/09/22 10:11:25": datetime(2026, 9, 22, 10, 11),
    }
    for raw, want in cases.items():
        dt, _, has_time = parse_datetime(raw)
        assert dt == want and has_time, raw


def test_won_formats():
    assert parse_won("금 40,000원") == 40000
    assert parse_won("₩120,000") == 120000
    assert parse_won("40000원") == 40000
    assert parse_won("96,000원  (20% 감경)") == 96000
    assert parse_won("12만원") == 120000
    assert parse_won("3만 2천원") == 32000
    assert parse_won(None) is None


def test_plate_and_accounts():
    assert normalize_plate("18노 6336 (승용)") == "18노6336"
    assert normalize_plate("123가4567") == "123가4567"
    accs = parse_accounts("NH농협은행 025-1618-3537-75 | KB국민은행 368570-62-249741")
    assert [(a["bank"], a["digits"]) for a in accs] == [("NH농협은행", "0251618353775"), ("KB국민은행", "36857062249741")]
    assert parse_accounts("계좌 없음") == []
