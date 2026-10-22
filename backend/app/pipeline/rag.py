"""3단계 근거 찾기 (RAG).

1) 할 일 단계마다 정해 둔 조문을 먼저 붙인다 (STEP_LAWS) — 틀릴 수 없는 길.
2) 매핑이 없는 질문은 글자 2-gram TF-IDF 코사인 유사도로 찾는다 — 외부 API 없이 도는 벡터 검색.
   법령이 수십 건으로 늘면 같은 search() 자리에 임베딩 + Supabase pgvector 를 끼우면 된다.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "laws.json"

STEP_LAWS = {
    "PAY": ("L18", "L18-5"),
    "OBJECT": ("L16",),
    "REDUCE50": ("L2-2",),
    "OVERDUE": ("L24",),
    "OBJECT_LATE": ("L20",),
}
ALWAYS = ("F6",)  # 금액 설명은 항상 함께 보인다
PUBLIC_KEYS = ("id", "law", "article", "title", "excerpt", "plain", "source_url", "verified")


def _grams(text: str) -> list[str]:
    s = re.sub(r"\s+", "", text)
    return [s[i:i + 2] for i in range(len(s) - 1)]


class LawIndex:
    def __init__(self, path: Path = DATA):
        self.items: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        self.by_id = {it["id"]: it for it in self.items}
        docs = [_grams(" ".join([it["title"], it["plain"], it["excerpt"], " ".join(it.get("keywords", []))]))
                for it in self.items]
        n = len(docs)
        df = Counter(g for d in docs for g in set(d))
        self._idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self._vecs = [self._vector(d) for d in docs]

    def _vector(self, grams: list[str]) -> dict[str, float]:
        tf = Counter(grams)
        vec = {g: c * self._idf.get(g, 0.0) for g, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    def search(self, query: str, k: int = 2, min_score: float = 0.05) -> list[tuple[dict, float]]:
        q = self._vector(_grams(query))
        scored = [(it, sum(w * vec.get(g, 0.0) for g, w in q.items())) for it, vec in zip(self.items, self._vecs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self._public(it), s) for it, s in scored[:k] if s >= min_score]

    def get(self, ids) -> list[dict]:
        return [self._public(self.by_id[i]) for i in ids if i in self.by_id]

    def citations_for_steps(self, steps: list[dict]) -> list[dict]:
        ids: list[str] = []
        for s in steps:
            for cid in s.get("cites", []):
                if cid not in ids:
                    ids.append(cid)
        ids += [a for a in ALWAYS if a not in ids]
        return self.get(ids)

    @staticmethod
    def _public(it: dict) -> dict:
        return {k: it.get(k) for k in PUBLIC_KEYS}


@lru_cache(maxsize=1)
def law_index() -> LawIndex:
    return LawIndex()


def laws_for_step(step_type: str) -> list[str]:
    return list(STEP_LAWS.get(step_type, ()))
