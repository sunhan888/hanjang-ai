"""OpenAI 모델로 판독한다. strict JSON 스키마(response_format)로 형식을 강제한다.

OPENAI_MODEL 에는 이미지 입력과 json_schema 출력을 지원하는 모델 이름을 넣는다.
처음 연결할 때는 테스트셋 한 장으로 확인한다: python eval/run_batch.py --provider openai --limit 1
"""
from __future__ import annotations

import base64
import json

from .prompt import POLISH_PROMPT, SYSTEM_PROMPT, USER_PROMPT, extraction_schema, polish_schema


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 가 비어 있어요 (.env 확인).")
        if not model:
            raise RuntimeError("OPENAI_MODEL 을 정해 주세요 (이미지 입력과 json_schema 출력을 지원하는 모델).")
        from openai import OpenAI  # 선택 의존성

        self._client = OpenAI(api_key=api_key, timeout=90.0, max_retries=2)
        self.model = model

    def _json(self, messages: list, name: str, schema: dict, max_tokens: int) -> dict:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_schema",
                             "json_schema": {"name": name, "strict": True, "schema": schema}},
            max_completion_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        if not content:
            raise RuntimeError("모델이 빈 응답을 돌려줬어요.")
        return json.loads(content)

    def extract(self, jpeg: bytes, hint: str | None = None) -> dict:
        b64 = base64.standard_b64encode(jpeg).decode("ascii")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": USER_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
            ]},
        ]
        return self._json(messages, "record_notice", extraction_schema(), 2000)

    def polish(self, texts: list[str]) -> list[str] | None:
        messages = [{"role": "system", "content": POLISH_PROMPT},
                    {"role": "user", "content": json.dumps(texts, ensure_ascii=False)}]
        sentences = self._json(messages, "record_sentences", polish_schema(), 1500).get("sentences")
        return sentences if isinstance(sentences, list) else None
