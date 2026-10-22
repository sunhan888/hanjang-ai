import copy
import json
from datetime import date
from pathlib import Path

from app.fields import FIELDS
from app.pipeline.validate import validate

SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "app/data/sample_extraction.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 20)


def fields(**patch):
    """예시 판독 결과에서 일부 항목만 바꿔 validate 입력을 만든다. patch 키는 한국어 키."""
    by_key = {f.key: copy.deepcopy(SAMPLE["fields"][f.schema_key]) for f in FIELDS}
    for k, v in patch.items():
        by_key[k] = v
    return by_key


def test_clean_sample_passes():
    f, notes, dday, accounts = validate(fields(), TODAY)
    assert all(c.check is None for c in f.values())
    assert dday == {"deadline": "2026-11-03", "days_left": 14, "state": "upcoming", "today": "2026-10-20"}
    assert accounts[0]["bank"] == "우리은행"


def test_year_misread_is_caught_with_suggestion():
    f, *_ = validate(fields(위반일시={"raw": "2025.09.24(목) 11:14", "value": "2025-09-24 11:14", "label_seen": "위반 일시"}), TODAY)
    assert "1년 넘게" in f["위반일시"].check
    assert f["위반일시"].suggestion == "2026년 9월 24일(목) 오전 11시 14분"


def test_two_readings_disagree():
    f, *_ = validate(fields(위반일시={"raw": "26.09.24 11:14", "value": "2025-09-24 11:14", "label_seen": "위반 일시"}), TODAY)
    assert f["위반일시"].value == "2026-09-24 11:14"      # 코드가 raw 를 직접 읽은 값을 쓴다
    assert f["위반일시"].check == "두 번 읽은 날짜가 서로 달라요."


def test_reduction_amount_confusion():
    f, *_ = validate(fields(감경과태료={"raw": "24,000원", "value": "24000", "label_seen": "감경액"}), TODAY)
    assert "차액" in f["감경과태료"].check
    assert f["감경과태료"].suggestion == "96,000원"


def test_half_amount_confusion():
    f, *_ = validate(fields(감경과태료={"raw": "60,000원", "value": "60000", "label_seen": None}), TODAY)
    assert "50%" in f["감경과태료"].check


def test_missing_deadline_is_flagged_and_unknown():
    f, _, dday, _ = validate(fields(의견진술기한={"raw": None, "value": None, "label_seen": None}), TODAY)
    assert f["의견진술기한"].check == "종이에서 찾지 못했어요."
    assert dday["state"] == "unknown"


def test_deadline_before_issue_date():
    f, *_ = validate(fields(의견진술기한={"raw": "2026.10.02", "value": "2026-10-02", "label_seen": "의견제출기한"}), TODAY)
    assert f["의견진술기한"].check is not None


def test_illegal_fine_amount():
    f, *_ = validate(fields(과태료금액={"raw": "100,000원", "value": "100000", "label_seen": "과태료 금액"},
                            감경과태료={"raw": "80,000원", "value": "80000", "label_seen": None}), TODAY)
    assert "법에 정한 금액" in f["과태료금액"].check


def test_overdue_and_today_states():
    assert validate(fields(), date(2026, 11, 5))[2]["state"] == "overdue"
    assert validate(fields(), date(2026, 11, 3))[2]["state"] == "today"
