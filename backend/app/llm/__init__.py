"""판독기(LLM) 선택. 모든 판독기는 같은 두 메서드를 가진다.

    extract(jpeg: bytes, hint: str | None) -> dict   # prompt.extraction_schema() 모양
    polish(texts: list[str]) -> list[str] | None     # 선택: 쉬운 말 다듬기
"""
from __future__ import annotations

MOCK_MODES = ("mock", "mock-truth", "mock-noisy")


def make_provider(name: str, settings):
    name = (name or "mock").strip().lower()
    if name in MOCK_MODES:
        from .mock import MockProvider

        return MockProvider(mode=name)
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    if name == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    raise RuntimeError(f"알 수 없는 LLM_PROVIDER: {name} (mock, mock-truth, mock-noisy, anthropic, openai)")


def get_provider(settings):
    return make_provider(settings.llm_provider, settings)
