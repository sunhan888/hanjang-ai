"""Claude 로 판독한다. 도구 사용(tool use)을 강제해 스키마에 맞는 JSON 만 받는다.

문서: https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview
      https://docs.claude.com/en/docs/build-with-claude/vision
처음 연결할 때는 테스트셋 한 장으로 확인한다: python eval/run_batch.py --provider anthropic --limit 1
"""
from __future__ import annotations

import base64
import json

from .prompt import POLISH_PROMPT, SYSTEM_PROMPT, USER_PROMPT, extraction_schema, polish_schema


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 가 비어 있어요 (.env 확인).")
        import anthropic  # 선택 의존성: mock 만 쓸 때는 없어도 된다

        self._client = anthropic.Anthropic(api_key=api_key, timeout=90.0, max_retries=2)
        self.model = model

    def _tool_call(self, *, system: str, content, tool: str, schema: dict, max_tokens: int) -> dict:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[{"name": tool, "description": "결과를 정해진 형식으로 기록한다.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": tool},
            messages=[{"role": "user", "content": content}],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool:
                return dict(block.input)
        raise RuntimeError("모델이 결과를 도구로 돌려주지 않았어요.")

    def extract(self, jpeg: bytes, hint: str | None = None) -> dict:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(jpeg).decode("ascii")}},
            {"type": "text", "text": USER_PROMPT},
        ]
        return self._tool_call(system=SYSTEM_PROMPT, content=content, tool="record_notice",
                               schema=extraction_schema(), max_tokens=2000)

    def polish(self, texts: list[str]) -> list[str] | None:
        out = self._tool_call(system=POLISH_PROMPT, content=json.dumps(texts, ensure_ascii=False),
                              tool="record_sentences", schema=polish_schema(), max_tokens=1500)
        sentences = out.get("sentences")
        return sentences if isinstance(sentences, list) else None
