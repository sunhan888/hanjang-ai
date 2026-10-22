"""predictions.csv 를 정답표와 비교해 채점한다. 규칙은 docs/EVALUATION.md 참고.

  python eval/evaluate.py                       # 표준 출력
  python eval/evaluate.py --out eval/report.md  # 마크다운 리포트 파일로도 저장
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["문서종류", "발신기관", "증거번호", "위반차량", "위반일시", "위반장소",
          "위반내용", "과태료금액", "감경과태료", "의견진술기한", "가상계좌", "발행일"]
CORE = ["의견진술기한", "감경과태료", "가상계좌"]


def _nospace(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _accounts(s: str) -> set[str]:
    return {d for d in (_digits(p) for p in re.split(r"[|\n;,]+", s or "")) if len(d) >= 10}


def correct(field: str, truth: str, pred: str) -> bool:
    """항목별 정답 판정. 표기 차이는 봐주고 뜻이 다르면 틀린 것으로 본다."""
    t, p = (truth or "").strip(), (pred or "").strip()
    if not p:
        return False
    if field in ("과태료금액", "감경과태료"):
        return _digits(t) == _digits(p)
    if field in ("의견진술기한", "발행일", "위반일시"):
        return t == p
    if field in ("위반차량", "문서종류"):
        return _nospace(t) == _nospace(p)
    if field == "증거번호":
        return re.sub(r"[\s\-]", "", t) == re.sub(r"[\s\-]", "", p)
    if field == "가상계좌":  # 틀린 계좌가 하나도 없고, 맞는 계좌가 하나 이상
        tp, pp = _accounts(t), _accounts(p)
        return bool(pp) and pp <= tp
    if field == "발신기관":
        a, b = _nospace(t), _nospace(p)
        return a == b or (len(b) >= 4 and (a.endswith(b) or b.endswith(a)))
    a, b = _nospace(t), _nospace(p)  # 위반장소·위반내용
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.85


def pct(n: int, d: int) -> str:
    return f"{n / d * 100:.0f}% ({n}/{d})" if d else "-"


def load(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {row["파일명"]: row for row in csv.DictReader(fh)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", default=str(ROOT / "eval" / "testset" / "ground_truth.csv"))
    ap.add_argument("--pred", default=str(ROOT / "eval" / "predictions.csv"))
    ap.add_argument("--conditions", default=str(ROOT / "eval" / "testset" / "conditions.csv"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    truth, pred = load(Path(args.truth)), load(Path(args.pred))
    cond = load(Path(args.conditions)) if args.conditions and Path(args.conditions).is_file() else {}
    names = [n for n in truth if n in pred]

    field_ok = defaultdict(int)
    silent = []            # (파일, 항목, 정답, 예측): 틀렸는데 '확인 필요'도 없음
    caught = wrong = over = right_total = 0
    task_ok = 0
    errors = []
    per_trap = defaultdict(lambda: {"docs": 0, "task_ok": 0, "silent": 0})
    seconds = []

    for n in names:
        t, p = truth[n], pred[n]
        if p.get("seconds"):
            seconds.append(float(p["seconds"]))
        if p.get("error"):
            errors.append((n, p["error"]))
        doc_core_ok = True
        doc_silent = 0
        for f in FIELDS:
            ok = correct(f, t.get(f, ""), p.get(f, ""))
            flagged = bool(p.get(f"check_{f}"))
            if ok:
                field_ok[f] += 1
                right_total += 1
                over += flagged
            else:
                wrong += 1
                caught += flagged
                if not flagged:
                    silent.append((n, f, t.get(f, ""), p.get(f, "")))
                    doc_silent += 1
                if f in CORE:
                    doc_core_ok = False
        task_ok += doc_core_ok
        traps = [x for x in (cond.get(n, {}).get("함정") or "").split(",") if x and x != "-"] or ["없음"]
        for trap in traps:
            per_trap[trap]["docs"] += 1
            per_trap[trap]["task_ok"] += doc_core_ok
            per_trap[trap]["silent"] += doc_silent

    total = len(names)
    core_cells = total * len(CORE)
    core_silent = sum(1 for _, f, _, _ in silent if f in CORE)
    lines = [
        f"# 판독 평가 리포트 ({total}장)", "",
        "| 지표 | 값 | 목표 |", "| --- | --- | --- |",
        f"| 조용한 오답 (핵심 3항목) | {core_silent}건 / {core_cells}칸 | 0건 |",
        f"| 과업 성공 (핵심 3항목 모두 정답) | {pct(task_ok, total)} | 18/20 이상 |",
        f"| 오답을 '확인 필요'로 잡은 비율 | {pct(caught, wrong)} | 높을수록 좋음 |",
        f"| 과잉 경고 (맞았는데 확인 필요) | {pct(over, right_total)} | 10% 이하 |",
    ]
    if seconds:
        s = sorted(seconds)
        lines.append(f"| 처리 시간 중앙값 | {s[len(s) // 2]:.1f}초 | 20초 이하 |")
    lines += ["", "## 항목별 정확도", "", "| 항목 | 정확도 |", "| --- | --- |"]
    lines += [f"| {f}{' (핵심)' if f in CORE else ''} | {pct(field_ok[f], total)} |" for f in FIELDS]
    lines += ["", "## 함정별", "", "| 함정 | 장수 | 과업 성공 | 조용한 오답 |", "| --- | --- | --- | --- |"]
    for trap in sorted(per_trap):
        v = per_trap[trap]
        lines.append(f"| {trap} | {v['docs']} | {pct(v['task_ok'], v['docs'])} | {v['silent']}건 |")
    lines += ["", "## 조용한 오답 목록 (틀렸는데 확인 필요가 없던 칸)", ""]
    if silent:
        lines += ["| 파일 | 항목 | 정답 | 예측 |", "| --- | --- | --- | --- |"]
        lines += [f"| {n} | {f} | {t} | {p} |" for n, f, t, p in silent]
    else:
        lines.append("없음")
    if errors:
        lines += ["", "## 판독 실패", ""] + [f"- {n}: {e}" for n, e in errors]
    report = "\n".join(lines)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
