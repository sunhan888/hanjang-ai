"""API 계약 — 프론트와 AI 담당이 공유하는 결과 JSON 의 모양.

여기를 바꾸면 반드시 docs/API.md 를 함께 고치고,
backend/scripts/make_mock_results.py 로 frontend/mock/*.json 을 다시 만든다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

CONTRACT_VERSION = "1"


class FieldOut(BaseModel):
    value: Any = None             # 정규화 값: 날짜 YYYY-MM-DD, 일시 YYYY-MM-DD HH:MM, 금액 정수(원)
    raw: str | None = None        # 종이에 적힌 그대로
    label_seen: str | None = None  # 종이에서 찾은 칸 이름. "(문장)"이면 본문 문장에서 찾음
    check: str | None = None      # '확인 필요' 사유. null 이면 검증 통과
    suggestion: str | None = None  # 검증이 제안하는 값(화면 표시용 문장)


class Account(BaseModel):
    bank: str
    number: str


class DDay(BaseModel):
    deadline: str | None = None
    days_left: int | None = None
    state: Literal["upcoming", "today", "overdue", "unknown"]
    today: str


class Step(BaseModel):
    type: str                     # VERIFY, CHECK, PAY, OBJECT, REDUCE50, OVERDUE, CALL, OBJECT_LATE, SCAM
    title: str
    body: str
    cites: list[str] = []


class Citation(BaseModel):
    id: str
    law: str
    article: str
    title: str
    excerpt: str
    plain: str
    source_url: str | None = None
    verified: bool = False        # 국가법령정보센터 원문과 대조했는지 (팀이 확인 후 true 로)


class Result(BaseModel):
    version: str = CONTRACT_VERSION
    doc_type: str
    issuer: str | None = None
    fields: dict[str, FieldOut]
    accounts: list[Account] = []
    dday: DDay
    summary: str
    steps: list[Step]
    citations: list[Citation] = []
    notes: list[str] = []


class Analysis(BaseModel):
    id: str
    status: Literal["processing", "done", "failed"]
    stage: Literal["reading", "checking", "planning", "done"] | None = None
    result: Result | None = None
    error_code: str | None = None     # UNREADABLE, UNSUPPORTED, LLM_ERROR ...
    error_reason: str | None = None   # UNREADABLE 일 때 blur | cut | glare
    error_message: str | None = None
    created_at: str
    expires_at: str
