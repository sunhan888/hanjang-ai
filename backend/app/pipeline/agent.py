"""4단계 실행계획 (Agent).

- 어떤 단계를 보일지는 상황(D-day 상태, 확인 필요 여부)으로 정한다: 카탈로그 밖의 행동은 만들지 않는다.
- 각 단계의 근거 조문은 law_search 도구(rag.py)로 붙인다.
- 문장은 템플릿으로 만들고, 원하면 LLM 이 쉬운 말로 다듬는다(AGENT_LLM_POLISH=1).
  다듬은 문장의 숫자가 원래 문장과 하나라도 다르면 원래 문장을 쓴다 (숫자 대조 가드).
"""
from __future__ import annotations

import re
from datetime import date

from ..fields import AFFECTS_PAYMENT, BY_KEY, CHECK_ORDER
from .normalize import fmt_dt, fmt_md, fmt_won
from .rag import laws_for_step
from .validate import Checked

CATALOG = ("VERIFY", "CHECK", "PAY", "OBJECT", "REDUCE50", "OVERDUE", "CALL", "OBJECT_LATE", "SCAM")


def _step(kind: str, title: str, body: str) -> dict:
    assert kind in CATALOG, kind
    return {"type": kind, "title": title, "body": body, "cites": laws_for_step(kind)}


def _label(key: str, c: Checked) -> str:
    if c.label_seen and not c.label_seen.startswith("("):
        return c.label_seen
    return BY_KEY[key].plain


def issuer_short(issuer: str | None) -> str:
    """'서울특별시 마포구청장' → '서울특별시 마포구청'."""
    if not issuer:
        return "기관"
    return re.sub(r"장$", "", issuer.strip())


def _account_text(accounts: list[dict]) -> str:
    if not accounts:
        return "종이에 적힌 계좌"
    a = accounts[0]
    return f"{a['bank']} {a['number']}".strip()


def _check_step(f: dict[str, Checked]) -> dict | None:
    flagged = [k for k in CHECK_ORDER if f[k].check]
    if not flagged:
        return None
    if len(flagged) == 1:
        k = flagged[0]
        body = f[k].check
        if k not in AFFECTS_PAYMENT:
            body += " 마감일과 낼 돈은 이 칸과 상관없어요."
        return _step("CHECK", f"종이의 '{_label(k, f[k])}' 칸을 확인해 주세요", body)
    names = ", ".join(f"'{_label(k, f[k])}'" for k in flagged[:3])
    more = f" 외 {len(flagged) - 3}칸" if len(flagged) > 3 else ""
    return _step("CHECK", f"종이에서 {len(flagged)}칸을 확인해 주세요", f"{names}{more} 칸이 이상하게 읽혔어요.")


def plan(f: dict[str, Checked], dday: dict, accounts: list[dict]) -> tuple[str, list[dict]]:
    """반환: (요약 문장, 할 일 단계 목록)."""
    steps: list[dict] = []
    state = dday["state"]
    deadline = date.fromisoformat(dday["deadline"]) if dday.get("deadline") else None
    fine = f["과태료금액"].parsed if isinstance(f["과태료금액"].parsed, int) else None
    reduced = f["감경과태료"].parsed if isinstance(f["감경과태료"].parsed, int) else None
    acc = _account_text(accounts)

    check = _check_step(f)
    if check:
        steps.append(check)

    if state in ("upcoming", "today", "unknown"):
        v = f["위반일시"]
        when = fmt_dt(v.parsed, v.has_time) if v.parsed and not v.check else "적힌 날짜"
        where = f["위반장소"].value or "적힌 장소"
        plate = re.sub(r"([가-힣])(\d{4})$", r"\1 \2", f["위반차량"].value) if f["위반차량"].value else "적힌"
        steps.append(_step("VERIFY", "적힌 내용이 맞는지 보기", f"{when}, {where}, {plate} 차량이 맞나요?"))

        due = "오늘 안에" if state == "today" else (f"{fmt_md(deadline)}까지" if deadline else "종이에 적힌 마감일까지")
        if reduced:
            pay_title = f"맞으면 {due} {fmt_won(reduced)} 내기"
            pay_body = f"은행 앱이나 ATM에서 {acc}에 보내면 끝나요."
        else:
            pay_title = f"맞으면 {due} 깎인 금액 내기"
            pay_body = "깎인 금액을 찾지 못했어요. 종이의 금액 칸을 확인해 주세요."
        if state == "today":
            pay_body += " 가상계좌는 밤이 되면 입금이 막힐 수 있으니 서두르세요."
        steps.append(_step("PAY", pay_title, pay_body))

        obj_due = "오늘까지" if state == "today" else (f"{fmt_md(deadline)}까지" if deadline else "마감일까지")
        steps.append(_step("OBJECT", f"억울하면 {obj_due} 의견 내기",
                           "고지서에 적힌 방법(우편·팩스·방문·누리집)으로 의견서를 보내요. "
                           "의견을 내면 보통 20% 감경은 받지 못해요."))
        steps.append(_step("REDUCE50", "이런 분은 더 줄어들 수 있어요",
                           "기초생활수급자, 한부모가족, 중증장애인, 국가유공자(상이 1~3급), 미성년자는 "
                           "증빙을 내고 감경을 요청할 수 있어요. 과태료를 밀린 적이 있으면 해당되지 않아요."))
    else:  # overdue
        money = f"원래 금액 {fmt_won(fine)}이" if fine else "원래 금액이"
        steps.append(_step("OVERDUE", "감경 기한이 지났어요",
                           f"{money} 적힌 과태료 부과 고지서가 따로 와요. 그 고지서의 기한 안에 내세요. "
                           "넘기면 3%가 더 붙고, 그 뒤 달마다 늘어요."))
        steps.append(_step("CALL", "빨리 끝내고 싶다면 문의처에 전화하기",
                           "종이 맨 아래 '문의' 번호로 전화하면 지금 낼 방법을 알려 주기도 해요."))
        steps.append(_step("OBJECT_LATE", "억울하면 새 고지서를 받고 60일 안에 이의 내기",
                           "원래 금액 고지서를 받은 날부터 60일 안에 서면으로 이의를 낼 수 있어요."))

    steps.append(_step("SCAM", "문자 속 링크로는 내지 마세요", "종이에 적힌 계좌나 위택스·이파인에서만 내세요."))
    return _summary(f, dday, deadline, fine, reduced), steps


def _summary(f, dday, deadline, fine, reduced) -> str:
    head = f"{issuer_short(f['발신기관'].value)}에서 보낸 주정차 위반 과태료 사전 안내문이에요."
    state, n = dday["state"], dday.get("days_left")
    if state == "upcoming" and deadline:
        body = f" 마감일은 {fmt_md(deadline)}로 {n}일 남았어요."
        if reduced:
            body += f" 이 날까지 {fmt_won(reduced)}을 내면 20%를 깎아 줘요."
    elif state == "today":
        body = " 오늘이 마감일이에요."
        if reduced:
            body += f" 오늘 안에 {fmt_won(reduced)}을 내면 20%를 깎아 줘요."
    elif state == "overdue" and deadline:
        body = f" 감경 마감일({fmt_md(deadline)})이 {-n}일 지났어요."
        if fine:
            body += f" 원래 금액 {fmt_won(fine)} 고지서가 따로 와요."
    else:
        body = " 마감일을 읽지 못했어요. 종이에서 마감일을 확인해 주세요."
    n_check = sum(1 for c in f.values() if c.check)
    if n_check:
        body += f" 확인이 필요한 칸이 {n_check}개 있어요."
    return head + body


# ---- LLM 문장 다듬기 (선택) ----

def _numbers(text: str) -> list[str]:
    return sorted(re.findall(r"\d+", text))


def guard(original: str, polished: str | None) -> str:
    """다듬은 문장의 숫자가 원래 문장과 같을 때만 받아들인다."""
    if not polished or not polished.strip():
        return original
    return polished.strip() if _numbers(polished) == _numbers(original) else original


def polish_steps(steps: list[dict], provider) -> list[dict]:
    texts = [t for s in steps for t in (s["title"], s["body"])]
    try:
        out = provider.polish(texts)
    except Exception:  # 다듬기는 선택 기능: 실패해도 원래 문장으로 간다
        return steps
    if not out or len(out) != len(texts):
        return steps
    it = iter(out)
    return [{**s, "title": guard(s["title"], next(it)), "body": guard(s["body"], next(it))} for s in steps]
