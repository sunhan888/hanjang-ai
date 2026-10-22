"""환경변수 설정.

backend/.env 또는 저장소 루트의 .env 를 읽는다 (예시는 .env.example).
키는 절대 저장소에 커밋하지 않는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 저장소 루트

try:  # python-dotenv 가 없어도 동작하게
    from dotenv import load_dotenv

    load_dotenv(ROOT / "backend" / ".env")
    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

# 한국은 서머타임이 없어 고정 오프셋으로 충분하다 (slim 이미지에 tzdata 가 없어도 됨)
KST = timezone(timedelta(hours=9))


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # mock | mock-truth | mock-noisy | anthropic | openai
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "")
    # 비어 있으면 메모리 저장소 (서버를 끄면 결과도 사라짐)
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    result_ttl_hours: int = int(os.getenv("RESULT_TTL_HOURS", "24"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    # 할 일 문장을 LLM 으로 한 번 더 다듬을지 (숫자 대조 가드가 붙어 있음)
    agent_polish: bool = _bool("AGENT_LLM_POLISH")
    # 시연·테스트용 '오늘' 고정 (예: 2026-10-20). 비우면 실제 한국 날짜
    today_override: str = os.getenv("TODAY", "").strip()
    cors_origins: tuple = tuple(o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip())

    def today(self) -> date:
        if self.today_override:
            return date.fromisoformat(self.today_override)
        return datetime.now(KST).date()


settings = Settings()
