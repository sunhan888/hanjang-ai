"""판독 결과 저장소. 사진은 저장하지 않고 결과 JSON 만 24시간 둔다.

SUPABASE_URL 과 SUPABASE_SERVICE_ROLE_KEY 가 있으면 Supabase(PostgREST), 없으면 메모리.
서비스 키는 서버에만 둔다. 프론트에 절대 넣지 않는다.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone


def _expired(row: dict) -> bool:
    exp = row.get("expires_at")
    if not exp:
        return False
    return datetime.fromisoformat(str(exp).replace("Z", "+00:00")) < datetime.now(timezone.utc)


class MemoryStore:
    name = "memory"

    def __init__(self):
        self._rows: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, row: dict) -> None:
        with self._lock:
            self._rows[row["id"]] = dict(row)

    def update(self, aid: str, **patch) -> None:
        with self._lock:
            if aid in self._rows:
                self._rows[aid].update(patch)

    def get(self, aid: str) -> dict | None:
        with self._lock:
            row = self._rows.get(aid)
            if row and _expired(row):
                del self._rows[aid]
                return None
            return dict(row) if row else None

    def delete(self, aid: str) -> bool:
        with self._lock:
            return self._rows.pop(aid, None) is not None


class SupabaseStore:
    name = "supabase"

    def __init__(self, url: str, key: str):
        import httpx

        self._base = f"{url}/rest/v1/analyses"
        self._headers = {"apikey": key,"Content-Type": "application/json"}
        self._http = httpx.Client(timeout=10.0)

    def create(self, row: dict) -> None:
        r = self._http.post(self._base, json=row, headers={**self._headers, "Prefer": "return=minimal"})
        r.raise_for_status()

    def update(self, aid: str, **patch) -> None:
        r = self._http.patch(self._base, params={"id": f"eq.{aid}"}, json=patch,
                             headers={**self._headers, "Prefer": "return=minimal"})
        r.raise_for_status()

    def get(self, aid: str) -> dict | None:
        r = self._http.get(self._base, params={"id": f"eq.{aid}", "select": "*"}, headers=self._headers)
        r.raise_for_status()
        rows = r.json()
        row = rows[0] if rows else None
        if row and _expired(row):
            self.delete(aid)
            return None
        return row

    def delete(self, aid: str) -> bool:
        r = self._http.delete(self._base, params={"id": f"eq.{aid}"}, headers=self._headers)
        r.raise_for_status()
        return True


def get_store(settings):
    if settings.supabase_url and settings.supabase_key:
        return SupabaseStore(settings.supabase_url, settings.supabase_key)
    return MemoryStore()
