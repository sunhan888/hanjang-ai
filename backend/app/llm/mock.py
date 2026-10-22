"""LLM 없이 도는 판독기 — 키 없이 화면·연동·평가를 개발하기 위한 것.

mode
- mock        : 어떤 사진이든 예시(notice_06) 판독 결과를 돌려준다. 프론트·서버 연동 개발용.
- mock-truth  : 테스트셋 파일명(hint)을 받으면 정답표 그대로 돌려준다. 파이프라인 상한 확인용.
- mock-noisy  : 정답표에 '실물에서 본 실수'를 함정별로 섞는다. 규칙 검증이 무엇을 잡고
                무엇을 놓치는지(조용한 오답) 보는 평가 연습용.
"""
from __future__ import annotations

import copy
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

from ..config import ROOT
from ..fields import BY_KEY, DOC_TYPE, FIELDS

DATA = Path(__file__).resolve().parents[1] / "data"
SAMPLE = json.loads((DATA / "sample_extraction.json").read_text(encoding="utf-8"))
TESTSET = ROOT / "eval" / "testset"


def _read_csv(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {row["파일명"]: row for row in csv.DictReader(fh)}


def _labels(printed: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for part in (printed or "").split(" ; "):
        if "=" in part:
            k, v = part.split("=", 1)
            v = v.strip()
            out[k.strip()] = None if v == "(라벨 없음)" else ("(문장)" if v == "(문장 속)" else v)
    return out


def _restyle(printed_fine: str, fine: int, amount: int) -> str:
    """'₩120,000' 같은 금액 표기 모양을 유지한 채 숫자만 바꾼다."""
    s = printed_fine.replace(f"{fine:,}", f"{amount:,}")
    return s.replace(str(fine), str(amount))


def _shift_year(value: str, delta: int) -> str:
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    return dt.replace(year=dt.year + delta).strftime("%Y-%m-%d %H:%M")


class MockProvider:
    def __init__(self, mode: str = "mock", testset_dir: Path = TESTSET):
        self.name = mode
        self.mode = mode
        self.delay = float(os.getenv("MOCK_DELAY_SEC", "0.8"))
        self._truth: dict[str, dict] | None = None
        self._cond: dict[str, dict] | None = None
        self.testset_dir = testset_dir

    def _load(self) -> None:
        if self._truth is None:
            self._truth = _read_csv(self.testset_dir / "ground_truth.csv")
            self._cond = _read_csv(self.testset_dir / "conditions.csv")

    def extract(self, jpeg: bytes, hint: str | None = None) -> dict:
        if self.delay:
            time.sleep(self.delay)
        if self.mode in ("mock-truth", "mock-noisy") and hint:
            self._load()
            if hint in self._truth:
                return self._from_testset(hint, noisy=self.mode == "mock-noisy")
        return copy.deepcopy(SAMPLE)

    def polish(self, texts: list[str]) -> list[str] | None:
        return None  # mock 은 문장을 다듬지 않는다

    def _from_testset(self, name: str, noisy: bool) -> dict:
        row, cond = self._truth[name], self._cond[name]
        labels = _labels(cond.get("인쇄 라벨", ""))
        fine, reduced = int(row["과태료금액"]), int(row["감경과태료"])
        printed_fine = cond.get("금액 표기") or f"{fine:,}원"
        deadline_raw = (cond.get("기한 표기") or row["의견진술기한"]).replace("(문장 속) ", "")
        raw = {
            "문서종류": (cond.get("인쇄 제목"), DOC_TYPE),
            "발신기관": (row["발신기관"], row["발신기관"]),
            "증거번호": (row["증거번호"], row["증거번호"]),
            "위반차량": (row["위반차량"], row["위반차량"]),
            "위반일시": (cond.get("위반일시 표기") or row["위반일시"], row["위반일시"]),
            "위반장소": (row["위반장소"], row["위반장소"]),
            "위반내용": (row["위반내용"], row["위반내용"]),
            "과태료금액": (printed_fine, str(fine)),
            "감경과태료": (_restyle(printed_fine, fine, reduced), str(reduced)),
            "의견진술기한": (deadline_raw, row["의견진술기한"]),
            "가상계좌": (row["가상계좌"], row["가상계좌"]),
            "발행일": (row["발행일"], row["발행일"]),
        }
        if noisy:
            traps = set(filter(None, (cond.get("함정") or "").split(",")))
            if "TS" in traps:      # 사진 속 장비 시각을 본문 대신 읽음 → 규칙으로는 못 잡는다
                stamp = cond["사진 속 시각"].split(" / ")[0]
                raw["위반일시"] = (stamp, stamp[:16].replace("/", "-").replace(".", "-"))
            if "YY" in traps:      # 두 자리 연도를 한 해 앞으로 오독
                v = _shift_year(row["위반일시"], -1)
                raw["위반일시"] = (v, v)
            if "XY" in traps:      # 연도 경계에서 발행 연도로 착각
                v = _shift_year(row["위반일시"], +1)
                raw["위반일시"] = (v, v)
            if "RD" in traps:      # 감경액(차액)을 감경 후 금액으로 오독
                diff = fine - reduced
                raw["감경과태료"] = (_restyle(printed_fine, fine, diff), str(diff))
            if "50" in traps:      # 50% 감경 예시 금액을 오독
                half = fine // 2
                raw["감경과태료"] = (_restyle(printed_fine, fine, half), str(half))
            if "SD" in traps:      # 문장 속 기한을 못 찾음
                raw["의견진술기한"] = (None, None)
            if "DN" in traps:      # 옆에 찍힌 다른 번호를 증거번호로 읽음
                raw["증거번호"] = ("교통지도과-" + row["증거번호"][-5:],) * 2
            if "MA" in traps:      # 계좌가 여러 개인데 첫 번째만 읽음
                first = row["가상계좌"].split(" | ")[0]
                raw["가상계좌"] = (first, first)
        fields = {}
        for f in FIELDS:
            r, v = raw[f.key]
            missing = r is None and v is None
            label = labels.get(f.key)
            fields[f.schema_key] = {"raw": r, "value": v, "label_seen": None if missing else label}
        return {"doc_type": DOC_TYPE, "is_parking_prenotice": True, "readable": True,
                "unreadable_reason": None, "fields": fields}


assert set(BY_KEY) == {f.key for f in FIELDS}
