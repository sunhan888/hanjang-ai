"""frontend/mock/*.json 을 실제 파이프라인으로 다시 만든다.

API 계약(schemas.py)이나 문장(agent.py)을 바꾼 뒤 실행:  python scripts/make_mock_results.py
프론트는 주소 뒤 ?mock, ?mock=check, ?mock=today, ?mock=overdue 로 이 파일들을 쓴다.
"""
import copy
import json
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("MOCK_DELAY_SEC", "0")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.mock import SAMPLE  # noqa: E402
from app.pipeline.run import analyze  # noqa: E402
from app.schemas import Result  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "mock"


class Static:
    name = "static"

    def __init__(self, ext):
        self.ext = ext

    def extract(self, jpeg, hint=None):
        return copy.deepcopy(self.ext)


check = copy.deepcopy(SAMPLE)  # 위반 일시 연도를 2025 로 잘못 읽은 경우
check["fields"]["violated_at"] = {"raw": "2025.09.24(목) 11:14", "value": "2025-09-24 11:14", "label_seen": "위반 일시"}

CASES = {
    "result": (SAMPLE, date(2026, 10, 20)),
    "result-check": (check, date(2026, 10, 20)),
    "result-today": (SAMPLE, date(2026, 11, 3)),
    "result-overdue": (SAMPLE, date(2026, 11, 5)),
}

OUT.mkdir(parents=True, exist_ok=True)
for name, (ext, today) in CASES.items():
    result = analyze(b"", Static(ext), today)
    Result.model_validate(result)  # 계약에 맞는지 확인
    (OUT / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{name}.json  state={result['dday']['state']}  steps={[s['type'] for s in result['steps']]}")
