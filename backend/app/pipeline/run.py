"""판독 파이프라인: ① 판독(LLM) → ② 규칙 검증(코드) → ③ 근거(RAG) → ④ 실행계획(Agent).

서버(main.py)와 일괄 평가(eval/run_batch.py)가 같은 함수를 쓴다.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from ..fields import DOC_TYPE, FIELDS
from ..schemas import CONTRACT_VERSION
from .agent import plan, polish_steps
from .rag import law_index
from .validate import validate

UNREADABLE_REASONS = ("blur", "cut", "glare")


class PipelineError(Exception):
    """사용자에게 다시 찍기·다른 문서 안내를 보여 줘야 하는 실패."""

    def __init__(self, code: str, message: str, reason: str | None = None):
        super().__init__(message)
        self.code, self.message, self.reason = code, message, reason


def analyze(jpeg: bytes, provider, today: date, hint: str | None = None,
            on_stage: Callable[[str], None] | None = None, polish: bool = False) -> dict:
    stage = on_stage or (lambda _s: None)

    stage("reading")
    ext = provider.extract(jpeg, hint=hint) or {}
    if not ext.get("readable", True):
        reason = ext.get("unreadable_reason")
        raise PipelineError("UNREADABLE", "사진의 글자를 읽기 어려워요.",
                            reason if reason in UNREADABLE_REASONS else "blur")
    if not ext.get("is_parking_prenotice", True):
        raise PipelineError("UNSUPPORTED", "아직 읽을 수 없는 문서예요.", ext.get("doc_type"))

    stage("checking")
    got = ext.get("fields") or {}
    raw_fields = {f.key: got.get(f.schema_key) or {} for f in FIELDS}
    checked, notes, dday, accounts = validate(raw_fields, today)

    stage("planning")
    summary, steps = plan(checked, dday, accounts)
    if polish and hasattr(provider, "polish"):
        steps = polish_steps(steps, provider)
    citations = law_index().citations_for_steps(steps)

    return {
        "version": CONTRACT_VERSION,
        "doc_type": DOC_TYPE,
        "issuer": checked["발신기관"].value,
        "fields": {k: c.to_api() for k, c in checked.items()},
        "accounts": [{"bank": a["bank"], "number": a["number"]} for a in accounts],
        "dday": dday,
        "summary": summary,
        "steps": steps,
        "citations": citations,
        "notes": notes,
    }
