"""테스트셋 이미지를 파이프라인에 돌려 predictions.csv 를 만든다 (서버 없이 함수 직접 호출).

예)
  python eval/run_batch.py --provider mock-noisy        # 키 없이 평가 흐름 연습
  python eval/run_batch.py --provider anthropic --limit 1   # 실제 모델 연결 확인 (1장)
  python eval/run_batch.py --provider anthropic         # 20장 전체 (비용 발생)
  python eval/run_batch.py --images eval/real --truth eval/real/ground_truth.csv   # 실물 견본
다음 단계: python eval/evaluate.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("MOCK_DELAY_SEC", "0")

from app.config import settings  # noqa: E402
from app.fields import KEYS  # noqa: E402
from app.llm import make_provider  # noqa: E402
from app.imaging import to_jpeg  # noqa: E402  (서버와 같은 전처리)
from app.pipeline.run import PipelineError, analyze  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock-noisy"))
    ap.add_argument("--images", default=str(ROOT / "eval" / "testset" / "images"))
    ap.add_argument("--truth", default=str(ROOT / "eval" / "testset" / "ground_truth.csv"),
                    help="파일 목록을 이 정답표 순서대로 돈다")
    ap.add_argument("--today", default="2026-10-20", help="D-day 계산 기준일 (평가는 날짜를 고정한다)")
    ap.add_argument("--out", default=str(ROOT / "eval" / "predictions.csv"))
    ap.add_argument("--limit", type=int, default=0, help="앞에서부터 N장만")
    args = ap.parse_args()

    provider = make_provider(args.provider, settings)
    with open(args.truth, encoding="utf-8-sig", newline="") as fh:
        names = [row["파일명"] for row in csv.DictReader(fh)]
    if args.limit:
        names = names[: args.limit]

    header = ["파일명", *KEYS, *[f"check_{k}" for k in KEYS], "error", "seconds"]
    rows = []
    for name in names:
        jpeg = to_jpeg((Path(args.images) / name).read_bytes())
        t0 = time.time()
        row = {"파일명": name}
        try:
            result = analyze(jpeg, provider, today=date.fromisoformat(args.today), hint=name)
            for k in KEYS:
                f = result["fields"][k]
                row[k] = "" if f["value"] is None else f["value"]
                row[f"check_{k}"] = f["check"] or ""
            row["error"] = ""
        except PipelineError as e:
            row["error"] = f"{e.code}:{e.reason or ''}"
        except Exception as e:  # 모델·네트워크 오류도 기록하고 다음 장으로
            row["error"] = f"EXCEPTION:{type(e).__name__}"
        row["seconds"] = f"{time.time() - t0:.1f}"
        rows.append(row)
        flags = sum(1 for k in KEYS if row.get(f"check_{k}"))
        print(f"{name}  {row['seconds']}s  확인필요 {flags}  {row['error']}")

    with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)}장 → {args.out}  (provider={args.provider})")


if __name__ == "__main__":
    main()
