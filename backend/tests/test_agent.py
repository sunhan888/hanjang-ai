from datetime import date

from app.llm.mock import MockProvider
from app.pipeline.agent import guard, polish_steps
from app.pipeline.run import PipelineError, analyze

TODAY = date(2026, 10, 20)


def types(result):
    return [s["type"] for s in result["steps"]]


def test_upcoming_plan():
    r = analyze(b"", MockProvider("mock"), TODAY)
    assert types(r) == ["VERIFY", "PAY", "OBJECT", "REDUCE50", "SCAM"]
    assert r["steps"][1]["title"] == "맞으면 11월 3일(화)까지 96,000원 내기"
    assert [c["id"] for c in r["citations"]] == ["L18", "L18-5", "L16", "L2-2", "F6"]


def test_overdue_plan():
    r = analyze(b"", MockProvider("mock"), date(2026, 11, 5))
    assert types(r) == ["OVERDUE", "CALL", "OBJECT_LATE", "SCAM"]
    assert "120,000원" in r["steps"][0]["body"]


def test_check_step_comes_first():
    p = MockProvider("mock")
    original = p.extract

    def broken(jpeg, hint=None):
        ext = original(jpeg, hint)
        ext["fields"]["reduced_fine"] = {"raw": "24,000원", "value": "24000", "label_seen": "감경액"}
        return ext

    p.extract = broken
    r = analyze(b"", p, TODAY)
    assert types(r)[0] == "CHECK"
    assert "확인이 필요한 칸이 1개" in r["summary"]


def test_unreadable_and_unsupported():
    class Bad:
        def __init__(self, ext):
            self.ext = ext

        def extract(self, jpeg, hint=None):
            return self.ext

    try:
        analyze(b"", Bad({"readable": False, "unreadable_reason": "cut"}), TODAY)
        raise AssertionError("PipelineError 가 나야 함")
    except PipelineError as e:
        assert (e.code, e.reason) == ("UNREADABLE", "cut")
    try:
        analyze(b"", Bad({"readable": True, "is_parking_prenotice": False, "doc_type": "자동차세"}), TODAY)
        raise AssertionError("PipelineError 가 나야 함")
    except PipelineError as e:
        assert e.code == "UNSUPPORTED"


def test_guard_rejects_changed_numbers():
    assert guard("11월 3일까지 96,000원", "11월 3일까지 9만 6천 원") == "11월 3일까지 96,000원"
    assert guard("11월 3일까지 96,000원", "11월 3일 전에 96,000원을 내요") == "11월 3일 전에 96,000원을 내요"


def test_polish_falls_back_on_wrong_length():
    class P:
        def polish(self, texts):
            return ["하나"]

    steps = [{"type": "SCAM", "title": "a", "body": "b", "cites": []}]
    assert polish_steps(steps, P()) == steps
