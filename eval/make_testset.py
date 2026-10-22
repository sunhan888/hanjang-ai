#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한장해결AI — 주정차위반 과태료 사전통지서 합성 테스트셋 생성기
================================================================

무엇을 만드나
  양식(레이아웃)과 라벨 표기를 서로 독립적으로 섞은 사전통지서 이미지 20장과 정답표.
  - 양식 3종   A 서울시형(세로·사진 2컷) / B 경찰서형(세로·사진 1컷) / C 시군 가로형(가로·사진 4컷)
  - 라벨 표기  항목마다 동의어 4개 중 하나를 샘플별로 무작위 선택. 같은 양식이 다른 라벨로,
               같은 라벨이 다른 양식으로 나오므로 '위치로 맞힌 것'과 '라벨로 맞힌 것'을 가를 수 있음
  - 함정 8종   실물 확인에서 나온 위험을 계획적으로 배치 (아래 TRAPS·PLAN 참고)
  - 열화 3단계 스캔본 / 조심해서 찍은 사진 / 기울고 그림자 진 사진

출력 (기본 ./testset)
  images/notice_01.jpg ~ notice_20.jpg   테스트 이미지
  ground_truth.csv                        정답표 12개 항목 (UTF-8 BOM — 엑셀에서 바로 열림)
  conditions.csv                          샘플별 변형 조건(양식·열화·함정·실제 인쇄된 라벨) — 오답 분석용
  contact_sheet.jpg                       20장 미리보기
  clean/notice_XX.png                     --save-clean 지정 시 열화 전 원본 (화질 영향 분리용)

사용
  pip install pillow numpy
  python make_testset.py                        # seed 42, 기준일 2026-10-20 → 언제 돌려도 같은 20장
  python make_testset.py --seed 7 --out ts_b    # 다른 20장
  python make_testset.py --font C:/Windows/Fonts/malgun.ttf

  한글 폰트는 자동으로 찾습니다(Windows 맑은 고딕·바탕 / macOS 애플 SD 고딕 / Linux 나눔·Noto CJK).
  못 찾으면 나눔고딕을 설치하거나 --font 로 .ttf 경로를 지정하세요.

정답표 표기 규칙 — 예측값도 같은 규칙으로 정규화한 뒤 비교하세요
  문서종류          분류값 고정 "주정차위반 과태료 사전통지서" (실제 인쇄된 제목은 conditions.csv)
  발신기관          서명란 명의 그대로 (예: 서울특별시 마포구청장)
  증거번호          인쇄된 그대로 — 비교할 때 공백·하이픈 제거
  위반차량          공백 없이 (예: 123가4567)
  위반일시          YYYY-MM-DD HH:MM, 24시간제. 기준은 '본문'이며 사진 속 타임스탬프가 아님
  위반장소·위반내용 본문에 인쇄된 그대로 — 부분일치나 유사도로 채점 권장
  과태료금액        정수(원)
  감경과태료        정수(원) = 의견진술기한 안에 자진납부할 때 낼 금액(20% 감경 '후'). 감경액(차액)이 아님
  의견진술기한·발행일 YYYY-MM-DD
  가상계좌          "은행 번호"를 " | "로 연결 — 비교할 때 은행별로 숫자만 대조

참고
  - 금액은 도로교통법 시행령 기준(일반 4만/5만, 소화전 주변 8만/9만, 어린이보호구역 12만/13만,
    동일 장소 2시간 이상 1만원 가산, 승용/승합)으로 맞췄습니다. RAG 근거 문서와 한 번 대조해 두세요.
  - 모든 이미지에 '견본' 워터마크와 '테스트용 합성 견본' 문구가 들어갑니다. 가짜 고지서로 악용되지
    않도록 일부러 넣은 것이니 지우지 마세요.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BICUBIC = getattr(Image, "Resampling", Image).BICUBIC
LANCZOS = getattr(Image, "Resampling", Image).LANCZOS
PERSPECTIVE = getattr(Image, "Transform", Image).PERSPECTIVE

# ══════════════════ 1. 테스트셋 구성 — 여기만 고쳐도 구성이 바뀝니다 ══════════════════
TEMPLATES = {"A": "서울시형(세로·사진2)", "B": "경찰서형(세로·사진1)", "C": "시군 가로형(가로·사진4)"}
LEVELS = {"clean": "스캔본", "light": "사진(약)", "heavy": "사진(강)"}
QUALITY = {"clean": 95, "light": 85, "heavy": 62}
TRAPS = {
    "TS": "사진 타임스탬프가 본문 위반일시와 다름",
    "YY": "본문 연도 2자리 표기(26.09.14)",
    "XY": "연도 경계(전년 12월 위반→1월 발행, 기한 이미 지남)",
    "RD": "감경액(차액)과 감경 후 금액을 함께 표기",
    "50": "50% 감경 대상자 금액 병기",
    "DN": "증거번호와 헷갈리는 번호 병기",
    "SD": "의견진술기한이 표 없이 문장 속에만 있음",
    "MA": "가상계좌 여러 개(은행별)",
}
PLAN = [  # (양식, 열화, 함정)
    ("A", "clean", []),            # 01 기준선
    ("A", "clean", ["MA"]),        # 02
    ("A", "clean", ["TS"]),        # 03
    ("A", "light", ["DN", "MA"]),  # 04
    ("A", "light", ["YY"]),        # 05
    ("A", "light", ["SD"]),        # 06
    ("A", "heavy", ["RD"]),        # 07
    ("A", "heavy", ["TS", "50"]),  # 08
    ("B", "clean", []),            # 09 기준선
    ("B", "clean", ["RD"]),        # 10
    ("B", "light", ["TS"]),        # 11
    ("B", "light", ["XY"]),        # 12
    ("B", "heavy", ["DN"]),        # 13
    ("B", "heavy", ["YY", "50"]),  # 14
    ("C", "clean", []),            # 15 기준선
    ("C", "clean", ["MA", "TS"]),  # 16
    ("C", "light", ["SD", "DN"]),  # 17
    ("C", "light", ["50"]),        # 18
    ("C", "heavy", ["XY"]),        # 19
    ("C", "heavy", ["RD", "YY"]),  # 20
]

FIELDS = ["문서종류", "발신기관", "증거번호", "위반차량", "위반일시", "위반장소",
          "위반내용", "과태료금액", "감경과태료", "의견진술기한", "가상계좌", "발행일"]
DOC_TYPE = "주정차위반 과태료 사전통지서"

# 항목별 라벨 동의어 — 샘플마다 하나씩 무작위로 골라 인쇄 (양식과 독립)
LABELS = {
    "증거번호": ["증거번호", "단속번호", "위반번호", "관리번호"],
    "위반차량": ["위반차량", "차량번호", "자동차등록번호", "위반차량번호"],
    "위반일시": ["위반일시", "단속일시", "적발일시", "위반 일시"],
    "위반장소": ["위반장소", "단속장소", "적발장소", "위반 장소"],
    "위반내용": ["위반내용", "위반사항", "위반행위", "위반 내용"],
    "과태료금액": ["과태료 금액", "부과금액", "과태료", "부과예정 과태료"],
    "감경과태료": ["감경 과태료", "자진납부 금액", "감경 시 납부금액", "기한 내 납부금액"],
    "의견진술기한": ["의견진술기한", "의견제출기한", "의견제출 기한", "자진납부 기한"],
    "가상계좌": ["가상계좌", "납부계좌", "입금전용계좌", "전용계좌"],
    "발행일": ["발행일", "발송일", "통지일", ""],  # "" = 라벨 없이 날짜만
}
TITLES = ["과태료 부과 사전통지서", "주정차위반 과태료 부과 사전통지서",
          "과태료 부과 사전통지 및 의견제출 안내", "주·정차위반 과태료 사전통지서"]
SUBTITLES = ["(의견진술 안내)", "(의견제출 및 자진납부 안내)", ""]

# (유형, 인쇄 문구 후보, 승용 금액, 승합 금액, 뽑힐 가중치)
VIOLATIONS = [
    ("일반", ["주정차 위반 (도로교통법 제32조)", "주·정차 금지장소 위반", "주차위반 (도로교통법 제33조)"],
     40000, 50000, 6),
    ("2시간 이상", ["주정차 위반 (동일 장소 2시간 이상)"], 50000, 60000, 1),
    ("어린이보호구역", ["어린이보호구역 내 주정차 위반", "어린이보호구역 주·정차 위반 (도로교통법 제32조)"],
     120000, 130000, 2),
    ("소방시설 주변", ["소방시설 주변 5m 이내 주정차 위반", "소화전 주변 주·정차 위반"], 80000, 90000, 2),
]

INTRO = {
    "A": ("귀하 소유의 차량이 아래와 같이 「도로교통법」을 위반하였기에 「질서위반행위규제법」 제16조에 따라 "
          "과태료 부과에 앞서 알려드립니다. 이의가 있으시면 {DL}까지 의견을 제출하여 주시고, "
          "같은 기한 안에 자진납부하시면 과태료의 20%를 감경해 드립니다."),
    "B": ("귀하의 차량이 아래와 같이 「도로교통법」을 위반하였으므로 「질서위반행위규제법」 제16조에 따라 "
          "과태료 부과 전에 미리 통지합니다. 의견이 있으면 {DL}까지 서면 또는 구두로 진술하여 주시기 바라며, "
          "그 기한 안에 자진납부하시면 과태료의 20%가 감경됩니다."),
    "C": ("아래 차량은 주·정차 금지 규정을 위반하여 과태료 부과 대상임을 미리 알려드립니다. "
          "{DL}까지 의견을 제출하실 수 있으며, 그 기한 안에 자진납부하시면 20% 감경된 금액으로 납부하실 수 있습니다."),
}
NOTE_50 = ("※ 기초생활수급자·한부모가족 보호대상자·중증장애인·국가유공자(상이등급 1~3급)·미성년자는 "
           "증빙서류를 제출하면 과태료의 50% 범위에서 감경받을 수 있습니다(질서위반행위규제법 시행령 제2조의2).")
PAY_NOTE = {
    "A": "※ 납부방법: 가상계좌 이체, 위택스(wetax.go.kr), 금융기관 CD/ATM. 의견진술기한이 지나면 과태료 부과 고지서가 별도로 발송됩니다.",
    "B": "※ 납부방법: 납부계좌 입금 또는 경찰청 교통민원24(efine.go.kr). 의견진술기한이 지나면 과태료 부과 고지서가 발송됩니다.",
    "C": "※ 납부방법: 가상계좌 이체, 위택스(wetax.go.kr), 금융기관 CD/ATM. 기한이 지나면 과태료 부과 고지서가 발송됩니다.",
}

# ══════════════════ 2. 가상 데이터 풀 ══════════════════
SEOUL = {  # 구: (도로명, 법정동)
    "마포구": (["월드컵로", "양화로", "독막로", "와우산로"], ["망원동", "합정동", "서교동", "연남동"]),
    "송파구": (["올림픽로", "송파대로", "백제고분로", "오금로"], ["잠실동", "가락동", "문정동", "방이동"]),
    "노원구": (["동일로", "노해로", "상계로", "공릉로"], ["상계동", "중계동", "하계동", "공릉동"]),
    "관악구": (["관악로", "남부순환로", "봉천로", "신림로"], ["봉천동", "신림동", "남현동"]),
    "강서구": (["공항대로", "화곡로", "강서로", "양천로"], ["화곡동", "등촌동", "가양동", "염창동"]),
    "은평구": (["통일로", "연서로", "은평로", "진흥로"], ["불광동", "응암동", "역촌동", "녹번동"]),
}
POLICE = [  # (경찰서, 관할 지역, 도로명, 법정동)
    ("서울마포경찰서", "서울특별시 마포구", ["월드컵로", "양화로", "마포대로"], ["공덕동", "아현동", "도화동"]),
    ("부산해운대경찰서", "부산광역시 해운대구", ["해운대해변로", "센텀중앙로", "좌동순환로"], ["우동", "중동", "좌동"]),
    ("대전둔산경찰서", "대전광역시 서구", ["둔산로", "대덕대로", "한밭대로"], ["둔산동", "탄방동", "월평동"]),
    ("수원남부경찰서", "경기도 수원시 권선구", ["권선로", "세권로", "경수대로"], ["권선동", "세류동", "곡반정동"]),
    ("광주서부경찰서", "광주광역시 서구", ["상무대로", "무진대로", "치평로"], ["치평동", "농성동", "화정동"]),
    ("청주흥덕경찰서", "충청북도 청주시 흥덕구", ["가경로", "직지대로", "2순환로"], ["가경동", "복대동", "봉명동"]),
]
CITIES = [  # (시, 지역, 도로명, 법정동)
    ("진주시", "경상남도 진주시", ["진주대로", "동진로", "에나로", "남강로"], ["평거동", "신안동", "가좌동", "충무공동"]),
    ("창원시", "경상남도 창원시 성산구", ["중앙대로", "원이대로", "창이대로"], ["상남동", "중앙동", "사파동"]),
    ("김해시", "경상남도 김해시", ["김해대로", "가야로", "호계로"], ["내동", "외동", "삼계동"]),
    ("전주시", "전북특별자치도 전주시 완산구", ["팔달로", "기린대로", "효자로"], ["효자동", "중화산동", "서신동"]),
    ("천안시", "충청남도 천안시 서북구", ["번영로", "불당대로", "충무로"], ["불당동", "쌍용동", "성정동"]),
]
NAMES = ["김○수", "이○영", "박○호", "최○진", "정○희", "강○민", "조○숙", "윤○식", "한○자", "임○철"]
HOME_ROADS = ["경기도 고양시 덕양구 화정로", "인천광역시 남동구 인하로", "경기도 성남시 분당구 정자일로",
              "서울특별시 도봉구 방학로", "대전광역시 유성구 대학로", "부산광역시 수영구 광안해변로",
              "경상남도 진주시 진양호로", "충청남도 아산시 배방로"]
BANKS = [("우리은행", "####-###-######"), ("신한은행", "###-###-######"), ("KB국민은행", "######-##-######"),
         ("NH농협은행", "###-####-####-##"), ("하나은행", "###-######-#####"), ("IBK기업은행", "###-######-##-###"),
         ("우체국", "######-##-######"), ("BNK경남은행", "###-##-#######")]
PLATE_LETTERS = "가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주"
AREA = [("서울", "02"), ("부산", "051"), ("대전", "042"), ("경기", "031"), ("광주", "062"),
        ("충청북", "043"), ("충청남", "041"), ("경상남", "055"), ("전북", "063")]
CAMS = ["CAM-07", "단속 3호기", "MOBILE-12", "고정식 #21", "UNIT 4"]
CAR_COLORS = [(232, 232, 234), (188, 190, 194), (38, 39, 43), (58, 78, 128), (148, 32, 36), (96, 100, 106)]
WD = "월화수목금토일"


# ══════════════════ 3. 표기 형식 ══════════════════
def fmt_date(d: date, style: str) -> str:
    y, m, dd, w = d.year, d.month, d.day, WD[d.weekday()]
    return {
        "dot": f"{y}.{m:02d}.{dd:02d}",
        "dot_sp": f"{y}. {m}. {dd}.",
        "dash": f"{y}-{m:02d}-{dd:02d}",
        "kor": f"{y}년 {m}월 {dd}일",
        "dot_wd": f"{y}.{m:02d}.{dd:02d}({w})",
        "kor_wd": f"{y}년 {m}월 {dd}일({w})",
        "yy_dot": f"{y % 100:02d}.{m:02d}.{dd:02d}",
        "yy_dot_sp": f"{y % 100:02d}. {m}. {dd}.",
    }[style]


def fmt_dt(t: datetime, style: str) -> str:
    if style == "kor":
        return f"{fmt_date(t.date(), 'kor')} {t.hour}시 {t.minute:02d}분"
    if style == "ampm":
        return f"{fmt_date(t.date(), 'dot')} {'오전' if t.hour < 12 else '오후'} {t.hour % 12 or 12:02d}:{t.minute:02d}"
    base = {"dot": "dot", "dash": "dash", "dot_wd": "dot_wd", "yy": "yy_dot"}[style]
    return f"{fmt_date(t.date(), base)} {t.hour:02d}:{t.minute:02d}"


def fmt_won(n: int, style: str) -> str:
    return {"comma": f"{n:,}원", "geum": f"금 {n:,}원", "sign": f"₩{n:,}", "plain": f"{n}원"}[style]


def area_code(region: str) -> str:
    return next((code for pre, code in AREA if region.startswith(pre)), "02")


# ══════════════════ 4. 샘플 내용과 정답 ══════════════════
def make_content(tpl: str, traps: list, rng: random.Random, base: date) -> dict:
    c: dict = {"tpl": tpl, "traps": traps}

    # 발신기관 · 관할 지역
    if tpl == "A":
        gu = rng.choice(sorted(SEOUL))
        roads, dongs = SEOUL[gu]
        region = f"서울특별시 {gu}"
        c.update(org_head=region, signer=f"서울특별시 {gu}청장", emblem=gu[:2], seal=f"{gu}청장인",
                 dept=rng.choice(["교통지도과", "주차관리과", "교통행정과"]))
        who = f"{gu} {c['dept']} 주정차단속팀"
    elif tpl == "B":
        station, region, roads, dongs = rng.choice(POLICE)
        c.update(org_head=station, signer=f"{station}장", emblem="경찰", seal=f"{station}장인",
                 dept=rng.choice(["교통안전계", "교통관리계"]))
        who = f"{station} {c['dept']}"
    else:
        city, region, roads, dongs = rng.choice(CITIES)
        c.update(org_head=city, signer=f"{city}장", emblem=city[:2], seal=f"{city}장지인",
                 dept=rng.choice(["교통행정과", "교통지도과", "주차관리과"]),
                 accent=rng.choice([(30, 112, 84), (22, 96, 120), (60, 92, 150)]))
        who = f"{city} {c['dept']}"
    # 국번이 0으로 시작하는 번호 = 실제로 존재하지 않는 전화번호
    c["contact"] = f"문의: {who} (전화 {area_code(region)}-0{rng.randint(100, 999)}-{rng.randint(1000, 9999)})"

    # 인쇄될 라벨 · 제목 · 수신인
    c["labels"] = {k: rng.choice(v) for k, v in LABELS.items()}
    c["title"], c["subtitle"] = rng.choice(TITLES), rng.choice(SUBTITLES)
    c["recipient"] = f"{rng.choice(NAMES)} 귀하"
    c["recipient_addr"] = (f"{rng.choice(HOME_ROADS)} {rng.randint(10, 300)}, "
                           f"{rng.randint(101, 115)}동 {rng.randint(1, 15)}{rng.randint(1, 4):02d}호")

    # 차량 (승용 01~69·100~699 / 승합 70~79·700~799 체계)
    kind = "승합" if rng.random() < 0.2 else "승용"
    if rng.random() < 0.6:
        front = rng.randint(100, 399) if kind == "승용" else rng.randint(700, 799)
    else:
        front = rng.randint(10, 69) if kind == "승용" else rng.randint(70, 79)
    letter, back = rng.choice(PLATE_LETTERS), rng.randint(1000, 9999)
    plate, spaced = f"{front}{letter}{back}", f"{front}{letter} {back}"
    c.update(kind=kind, plate_spaced=spaced, plate_print=spaced if rng.random() < 0.65 else plate,
             show_kind=rng.random() < 0.5, car_color=rng.choice(CAR_COLORS))

    # 위반 유형 · 금액
    vtype, texts, car_amt, van_amt, _ = rng.choices(VIOLATIONS, weights=[v[4] for v in VIOLATIONS])[0]
    amount = car_amt if kind == "승용" else van_amt
    reduced = amount * 8 // 10
    c.update(vtype=vtype, vtext=rng.choice(texts))

    # 날짜 — 위반 5~20일 뒤 발행, 발행 17~23일 뒤가 의견진술기한
    if "XY" in traps:
        issue = date(base.year, 1, rng.randint(5, 12))
        vday = issue - timedelta(days=rng.randint(13, 20))  # 항상 전년도 12월
    else:
        issue = base - timedelta(days=rng.randint(1, 12))
        vday = issue - timedelta(days=rng.randint(5, 20))
    hour = rng.randint(8, 19) if vtype == "어린이보호구역" else rng.randint(7, 22)
    viol = datetime(vday.year, vday.month, vday.day, hour, rng.randint(0, 59))
    deadline = issue + timedelta(days=rng.randint(17, 23))

    # 표기 형식
    if "YY" in traps:
        dt_style, d_style, i_style = "yy", rng.choice(["yy_dot", "yy_dot_sp"]), "yy_dot_sp"
    else:
        dt_style = rng.choice(["dot", "dash", "kor", "dot_wd", "ampm"])
        d_style = rng.choice(["dot", "dot_sp", "kor", "dot_wd", "dash"])
        i_style = rng.choice(["dot_sp", "kor", "dot"])
    w_style = rng.choice(["comma", "comma", "geum", "sign", "plain"])
    p = {"dt": fmt_dt(viol, dt_style), "deadline": fmt_date(deadline, d_style),
         "issue": fmt_date(issue, i_style), "amount": fmt_won(amount, w_style),
         "reduced": fmt_won(reduced, w_style), "reduction": fmt_won(amount - reduced, w_style),
         "half": fmt_won(amount // 2, w_style)}
    until = ("까지" if d_style == "kor" else " 까지") if rng.random() < 0.35 else ""
    p["deadline_cell"] = p["deadline"] + until
    c["p"] = p

    # 위반장소 (사진 오버레이에는 짧은 주소만)
    road, num = rng.choice(roads), rng.randint(3, 480)
    suffix = "○○초등학교 앞" if vtype == "어린이보호구역" else rng.choice(["앞", "앞 도로", "인근", "맞은편"])
    if rng.random() < 0.6:
        c["place"], c["overlay_loc"] = f"{region} {road} {num} {suffix}", f"{road} {num}"
    else:
        dong, n1, n2 = rng.choice(dongs), rng.randint(10, 999), rng.randint(1, 40)
        c["place"], c["overlay_loc"] = f"{region} {dong} {n1}-{n2} {suffix}", f"{dong} {n1}-{n2}"

    # 증거번호 + 헷갈리는 번호(DN)
    c["evid"] = rng.choice([
        f"{viol.year}-{rng.randint(1000, 9999)}-{rng.randint(1, 999999):07d}",
        f"{viol.year % 100:02d}{viol.month:02d}{viol.day:02d}-{rng.randint(1, 99999):05d}",
        f"E{viol.year}{rng.randint(10_000_000, 99_999_999)}",
        f"{rng.randint(100, 999)}-{viol.year}-{rng.randint(10000, 99999)}",
    ])
    c["distractors"] = []
    if "DN" in traps:
        pool = [("문서번호", f"{c['dept']}-{rng.randint(10000, 99999)}"),
                ("전자납부번호", f"{rng.randint(1000, 9999)}-{issue.year}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"),
                ("접수번호", f"{issue.year}{rng.randint(100000, 999999)}")]
        c["distractors"] = rng.sample(pool, rng.randint(1, 2))

    # 가상계좌 (숫자는 무작위 — 실제 계좌 아님)
    banks = rng.sample(BANKS, rng.randint(3, 4) if "MA" in traps else 1)
    c["accounts"] = [(b, "".join(str(rng.randint(0, 9)) if ch == "#" else ch for ch in pat)) for b, pat in banks]

    # 단속 사진 타임스탬프 — 평소엔 첫 사진 = 본문 위반일시, TS면 어느 사진에도 본문 시각이 없음
    n_ph = {"A": 2, "B": 1, "C": 4}[tpl]
    lo, hi = (121, 150) if vtype == "2시간 이상" else (3, 16)
    if "TS" in traps:
        offs = sorted(rng.sample(range(max(4, lo), hi + 10), n_ph))
    else:
        offs = [0] + sorted(rng.sample(range(lo, hi), n_ph - 1))
    fmt = rng.choice(["%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S"])
    c["stamps"] = [(viol + timedelta(minutes=o, seconds=rng.randint(1, 59))).strftime(fmt) for o in offs]
    c["cam"] = rng.choice(CAMS)
    c["gray_photos"] = rng.random() < 0.5

    # 안내문 · 도입문
    c["notes"] = [NOTE_50, PAY_NOTE[tpl]]
    if "50" in traps:
        c["notes"].append(f"※ 위 감경대상자에 해당하면 증빙서류 제출 후 50% 감경된 {p['half']}을 납부하시면 됩니다.")
    if "SD" in traps:
        c["dl_sentence"] = fmt_date(deadline, "yy_dot" if "YY" in traps else "kor_wd")
        c["intro"] = INTRO[tpl].format(DL=c["dl_sentence"])
    else:
        c["dl_sentence"] = ""
        c["intro"] = INTRO[tpl].format(DL=c["labels"]["의견진술기한"])

    # 정답
    c["gt"] = {
        "문서종류": DOC_TYPE,
        "발신기관": c["signer"],
        "증거번호": c["evid"],
        "위반차량": plate,
        "위반일시": viol.strftime("%Y-%m-%d %H:%M"),
        "위반장소": c["place"],
        "위반내용": c["vtext"],
        "과태료금액": amount,
        "감경과태료": reduced,
        "의견진술기한": deadline.isoformat(),
        "가상계좌": " | ".join(f"{b} {n}" for b, n in c["accounts"]),
        "발행일": issue.isoformat(),
    }
    used = {"문서종류": "(제목)", "발신기관": "(서명란)"}
    for f in FIELDS[2:]:
        used[f] = c["labels"][f] or "(라벨 없음)"
    if "SD" in traps:
        used["의견진술기한"] = "(문장 속)"
    if "RD" in traps:
        used["감경과태료"] = "감경 후 납부금액"
    c["labels_used"] = used
    return c


def check(c: dict) -> None:
    g = c["gt"]
    v = datetime.strptime(g["위반일시"], "%Y-%m-%d %H:%M").date()
    i, d = date.fromisoformat(g["발행일"]), date.fromisoformat(g["의견진술기한"])
    assert v < i < d, f"날짜 순서 오류: {g}"
    assert g["감경과태료"] == g["과태료금액"] * 8 // 10, f"감경 금액 오류: {g}"


# ══════════════════ 5. 그리기 도구 ══════════════════
INK, GRAY, LINE = (28, 28, 32), (104, 104, 110), (72, 72, 78)
PAPER, WHITE = (253, 253, 250), (255, 255, 255)
W_P, H_P, W_L, H_L, M = 1240, 1754, 1754, 1240, 70  # A4 150dpi 세로/가로, 여백


class Fonts:
    CANDIDATES = {
        "gothic": [("C:/Windows/Fonts/malgun.ttf", 0),
                   ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
                   ("/Library/Fonts/NanumGothic.ttf", 0),
                   (str(Path.home() / "Library/Fonts/NanumGothic.ttf"), 0),
                   ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
                   ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),
                   ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 1)],
        "gothic_bold": [("C:/Windows/Fonts/malgunbd.ttf", 0),
                        ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0),
                        ("/Library/Fonts/NanumGothicBold.ttf", 0),
                        (str(Path.home() / "Library/Fonts/NanumGothicBold.ttf"), 0),
                        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
                        ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 1)],
        "serif": [("C:/Windows/Fonts/batang.ttc", 0),
                  ("/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf", 0),
                  ("/Library/Fonts/NanumMyeongjo.ttf", 0),
                  (str(Path.home() / "Library/Fonts/NanumMyeongjo.ttf"), 0),
                  ("/System/Library/Fonts/Supplemental/AppleMyungjo.ttf", 0),
                  ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 1),
                  ("/usr/share/fonts/noto-cjk/NotoSerifCJK-Regular.ttc", 1)],
        "serif_bold": [("/usr/share/fonts/truetype/nanum/NanumMyeongjoBold.ttf", 0),
                       ("/Library/Fonts/NanumMyeongjoBold.ttf", 0),
                       (str(Path.home() / "Library/Fonts/NanumMyeongjoBold.ttf"), 0),
                       ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 1),
                       ("/usr/share/fonts/noto-cjk/NotoSerifCJK-Bold.ttc", 1)],
    }

    def __init__(self, overrides: dict):
        self.paths, self.cache = {}, {}
        for role, cands in self.CANDIDATES.items():
            if overrides.get(role):
                if not Path(overrides[role]).exists():
                    sys.exit(f"폰트 파일이 없습니다: {overrides[role]}")
                self.paths[role] = (overrides[role], 0)
            else:
                self.paths[role] = next(((p, i) for p, i in cands if Path(p).exists()), None)
        if not self.paths["gothic"]:
            sys.exit("한글 폰트를 찾지 못했습니다. 나눔고딕을 설치하거나 --font 로 .ttf 경로를 지정하세요.")

    def get(self, size: int, bold: bool = False, serif: bool = False):
        """(ImageFont, 가짜굵게) — 굵은 글꼴이 없으면 보통 글꼴에 획을 덧그려 흉내냄"""
        key = (size, bold, serif)
        if key not in self.cache:
            fam = "serif" if serif and self.paths["serif"] else "gothic"
            src, faux = self.paths.get(fam + ("_bold" if bold else "")), False
            if src is None:
                src, faux = self.paths[fam], bold
            self.cache[key] = (ImageFont.truetype(src[0], size, index=src[1]), faux)
        return self.cache[key]


class Pen:
    def __init__(self, img: Image.Image, fonts: Fonts, serif: bool = False):
        self.img, self.d, self.fonts, self.serif = img, ImageDraw.Draw(img), fonts, serif

    def text(self, xy, s, size, bold=False, fill=INK, anchor="la"):
        font, faux = self.fonts.get(size, bold, self.serif)
        extra = {"stroke_width": 1, "stroke_fill": fill} if faux else {}
        self.d.text(xy, s, font=font, fill=fill, anchor=anchor, **extra)

    def width(self, s, size, bold=False):
        font, faux = self.fonts.get(size, bold, self.serif)
        return font.getlength(s) + (2 if faux else 0)

    def wrap(self, s, size, max_w, bold=False):
        lines, cur = [], ""
        for word in s.split(" "):
            cand = f"{cur} {word}" if cur else word
            if self.width(cand, size, bold) <= max_w:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            while self.width(word, size, bold) > max_w:  # 한 단어가 칸보다 길면 글자 단위로 자름
                k = len(word) - 1
                while k > 1 and self.width(word[:k], size, bold) > max_w:
                    k -= 1
                lines.append(word[:k])
                word = word[k:]
            cur = word
        if cur:
            lines.append(cur)
        return lines or [""]

    def para(self, x, y, s, size, max_w, line_h=None, fill=INK):
        line_h = line_h or int(size * 1.55)
        for ln in self.wrap(s, size, max_w):
            self.text((x, y + line_h // 2), ln, size, fill=fill, anchor="lm")
            y += line_h
        return y

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self.d.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=width)

    def line(self, x0, y0, x1, y1, fill=INK, width=1):
        self.d.line([x0, y0, x1, y1], fill=fill, width=width)


def _lines(pen, x, y, h, lines, size, lh, bold=False, anchor="lm", fill=INK):
    y0 = y + (h - len(lines) * lh) / 2 + lh / 2
    for k, ln in enumerate(lines):
        pen.text((x, y0 + k * lh), ln, size, bold=bold, fill=fill, anchor=anchor)


def kv_table(pen, x, y, w, rows, label_w, size, label_bg, pad=10, min_h=48):
    """라벨 | 값 2열 표 (서울시형). 값의 \\n 은 줄바꿈"""
    lh = int(size * 1.45)
    for label, value in rows:
        vlines = [ln for part in str(value).split("\n") for ln in pen.wrap(part, size, w - label_w - 2 * pad)]
        llines = pen.wrap(label, size, label_w - 2 * pad, bold=True)
        h = max(min_h, max(len(vlines), len(llines)) * lh + 2 * pad)
        pen.rect(x, y, x + label_w, y + h, fill=label_bg, outline=LINE)
        pen.rect(x + label_w, y, x + w, y + h, outline=LINE)
        _lines(pen, x + label_w // 2, y, h, llines, size, lh, bold=True, anchor="mm")
        _lines(pen, x + label_w + pad, y, h, vlines, size, lh)
        y += h
    return y


def grid_row(pen, x, y, cells, size, label_bg, pad=10, min_h=48):
    """한 줄짜리 격자 (경찰서형). cells = [(글자, 폭, 라벨여부)]"""
    lh = int(size * 1.45)
    wrapped = [pen.wrap(t, size, cw - 2 * pad, bold=lab) for t, cw, lab in cells]
    h = max(min_h, max(len(ls) for ls in wrapped) * lh + 2 * pad)
    cx = x
    for (t, cw, lab), ls in zip(cells, wrapped):
        pen.rect(cx, y, cx + cw, y + h, fill=label_bg if lab else None, outline=LINE)
        if lab:
            _lines(pen, cx + cw // 2, y, h, ls, size, lh, bold=True, anchor="mm")
        else:
            _lines(pen, cx + pad, y, h, ls, size, lh)
        cx += cw
    return y + h


def stacked_grid(pen, x, y, w, items, size, label_bg, cols=2, pad=10):
    """라벨 띠 아래에 값이 오는 격자 (가로형). items = [(라벨, 값, 칸수)]"""
    lh, band, cw = int(size * 1.4), int(size * 1.75), w // cols
    rows, row, used = [], [], 0
    for label, value, span in items:
        if used + span > cols:
            rows.append(row)
            row, used = [], 0
        row.append([label, value, span])
        used += span
    if row:
        rows.append(row)
    for row in rows:
        row[-1][2] += cols - sum(s for _, _, s in row)  # 빈칸 없이 마지막 칸을 늘림
        vh = max(len(pen.wrap(v, size, cw * s - 2 * pad)) for _, v, s in row) * lh + 2 * pad
        cx = x
        for label, value, span in row:
            ww = cw * span
            pen.rect(cx, y, cx + ww, y + band, fill=label_bg, outline=LINE)
            pen.text((cx + pad, y + band // 2), label, size - 2, bold=True, anchor="lm")
            pen.rect(cx, y + band, cx + ww, y + band + vh, outline=LINE)
            _lines(pen, cx + pad, y + band, vh, pen.wrap(value, size, ww - 2 * pad), size, lh)
            cx += ww
        y += band + vh
    return y


def account_table(pen, x, y, w, label, accounts, size, label_bg, pad=10, rh=44, bw=170):
    pen.rect(x, y, x + bw, y + rh, fill=label_bg, outline=LINE)
    pen.text((x + bw // 2, y + rh // 2), "은행", size, bold=True, anchor="mm")
    pen.rect(x + bw, y, x + w, y + rh, fill=label_bg, outline=LINE)
    pen.text((x + bw + pad, y + rh // 2), label, size, bold=True, anchor="lm")
    y += rh
    for bank, num in accounts:
        pen.rect(x, y, x + bw, y + rh, outline=LINE)
        pen.text((x + bw // 2, y + rh // 2), bank, size, anchor="mm")
        pen.rect(x + bw, y, x + w, y + rh, outline=LINE)
        pen.text((x + bw + pad, y + rh // 2), num, size, anchor="lm")
        y += rh
    return y


def emblem(pen, cx, cy, r, text, fill, ring=WHITE):
    """기관 상징 자리 — 실제 로고가 아닌 원형 표시"""
    pen.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    pen.d.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4], outline=ring, width=2)
    pen.text((cx, cy), text, int(r * 0.72), bold=True, fill=ring, anchor="mm")


def stamp_seal(img, cx, cy, size, text, fonts, rng):
    """붉은 직인 — 오른쪽 열부터 세로쓰기"""
    n = len(text)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    red, bw = (196, 32, 36, 215), max(3, size // 20)
    d.rectangle([bw // 2, bw // 2, size - bw // 2 - 1, size - bw // 2 - 1], outline=red, width=bw)
    cell = (size - 4 * bw) / max(cols, rows)
    font, _ = fonts.get(max(8, int(cell * 0.86)), bold=True, serif=True)
    x_right, y_top = size / 2 + cell * cols / 2, size / 2 - cell * rows / 2
    for k, ch in enumerate(text):
        col, row = divmod(k, rows)
        d.text((x_right - (col + 0.5) * cell, y_top + (row + 0.5) * cell), ch, font=font, fill=red, anchor="mm")
    layer = layer.rotate(rng.uniform(-6, 6), resample=BICUBIC)
    img.paste(layer, (int(cx - size / 2), int(cy - size / 2)), layer)


def signature(img, pen, fonts, rng, c, cx, y, size=34):
    """발행일 + 기관장 명의 + 직인 (높이 약 130px)"""
    label, issue = c["labels"]["발행일"], c["p"]["issue"]
    pen.text((cx, y + 20), f"{label}: {issue}" if label else issue, 23, anchor="mm")
    sy = y + 84
    pen.text((cx, sy), c["signer"], size, bold=True, anchor="mm")
    stamp_seal(img, cx + pen.width(c["signer"], size, bold=True) / 2 + 14, sy, 86, c["seal"], fonts, rng)


def footer(pen, w, h, c):
    pen.text((M, h - 36), c["contact"], 16, fill=GRAY, anchor="lm")
    pen.text((w - M, h - 36), "※ 테스트용 합성 견본 — 실제 고지서가 아닙니다", 16, fill=GRAY, anchor="rm")


def watermark(img, fonts):
    w, h = img.size
    s = min(w, h)
    font, _ = fonts.get(int(s * 0.13), bold=True)
    tile = Image.new("RGBA", (int(s * 1.3), int(s * 0.3)), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((tile.width // 2, tile.height // 2), "견본 SAMPLE", font=font,
                              fill=(110, 110, 110, 30), anchor="mm")
    tile = tile.rotate(28, expand=True, resample=BICUBIC)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(tile, ((w - tile.width) // 2, (h - tile.height) // 2), tile)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _shade(color, k):
    return tuple(max(0, min(255, int(v * k))) for v in color)


def draw_car(d, cx, by, cw, color, plate, fonts):
    """뒤에서 본 승용차. cx=중심 x, by=바닥 y, cw=차폭"""
    ch = int(cw * 0.62)
    top, roof = by - int(ch * 0.56), by - ch
    ww, wh = int(cw * 0.14), int(ch * 0.2)
    for x0 in (cx - cw // 2 + int(cw * 0.04), cx + cw // 2 - int(cw * 0.04) - ww):
        d.rectangle([x0, by - wh // 2, x0 + ww, by + wh // 3], fill=(22, 22, 24))
    d.polygon([(cx - int(cw * 0.40), top + 2), (cx + int(cw * 0.40), top + 2),
               (cx + int(cw * 0.31), roof), (cx - int(cw * 0.31), roof)], fill=_shade(color, 0.85))
    d.polygon([(cx - int(cw * 0.35), top - int(ch * 0.04)), (cx + int(cw * 0.35), top - int(ch * 0.04)),
               (cx + int(cw * 0.28), roof + int(ch * 0.07)), (cx - int(cw * 0.28), roof + int(ch * 0.07))],
              fill=(44, 52, 62))
    d.rounded_rectangle([cx - cw // 2, top, cx + cw // 2, by], radius=max(2, int(cw * 0.05)),
                        fill=color, outline=_shade(color, 0.6), width=2)
    ly0, ly1 = top + int(ch * 0.06), top + int(ch * 0.19)
    d.rectangle([cx - cw // 2 + int(cw * 0.03), ly0, cx - cw // 2 + int(cw * 0.2), ly1], fill=(176, 28, 30))
    d.rectangle([cx + cw // 2 - int(cw * 0.2), ly0, cx + cw // 2 - int(cw * 0.03), ly1], fill=(176, 28, 30))
    pw = int(cw * 0.36)
    ph = max(8, int(pw * 0.22))
    px, py = cx - pw // 2, by - int(ch * 0.3)
    d.rectangle([px, py, px + pw, py + ph], fill=(246, 246, 246), outline=(30, 30, 30), width=max(1, ph // 12))
    font, _ = fonts.get(max(7, int(ph * 0.7)), bold=True)
    d.text((cx, py + ph // 2), plate, font=font, fill=(16, 16, 16), anchor="mm")


def evidence_photo(w, h, rng, nrng, fonts, c, k, closeup=False, gray=False):
    """단속 사진 흉내 — 건물·인도·황색 실선·차량 뒷모습 + 장비 타임스탬프 오버레이 (k = 사진 순번)"""
    img = Image.new("RGB", (w, h), (84, 86, 90))
    d = ImageDraw.Draw(img)
    color, plate = c["car_color"], c["plate_spaced"]
    if closeup:
        d.rectangle([0, 0, w, int(h * 0.35)], fill=rng.choice([(150, 146, 140), (120, 124, 130)]))
        draw_car(d, w // 2 + rng.randint(-w // 20, w // 20), int(h * 0.97),
                 min(int(w * rng.uniform(0.95, 1.12)), int(h * 1.55)), color, plate, fonts)
    else:
        hz = int(h * rng.uniform(0.40, 0.48))
        d.rectangle([0, 0, w, hz], fill=rng.choice([(170, 186, 202), (192, 196, 200), (146, 154, 166)]))
        x = -rng.randint(0, 40)
        while x < w:
            bw, bh = rng.randint(max(20, int(w * 0.14)), max(30, int(w * 0.32))), rng.randint(int(hz * 0.5), hz)
            col = rng.choice([(150, 140, 130), (120, 125, 135), (172, 162, 146), (104, 108, 114), (186, 181, 171)])
            d.rectangle([x, hz - bh, x + bw, hz], fill=col)
            for wy in range(hz - bh + 8, hz - 14, max(14, h // 16)):
                for wx in range(x + 6, x + bw - 12, max(14, w // 28)):
                    d.rectangle([wx, wy, wx + max(5, w // 60), wy + max(6, h // 30)], fill=_shade(col, 0.7))
            x += bw + rng.randint(0, 6)
        sw = int(h * 0.08)
        d.rectangle([0, hz, w, hz + sw], fill=(176, 174, 168))
        d.line([0, hz + sw, w, hz + sw], fill=(96, 96, 96), width=3)
        lw = max(2, h // 90)
        yl = hz + sw + max(4, h // 40)
        d.line([0, yl, w, yl], fill=(220, 184, 42), width=lw)  # 황색 실선 = 주정차 금지
        if rng.random() < 0.6:
            d.line([0, yl + 3 * lw, w, yl + 3 * lw], fill=(220, 184, 42), width=lw)
        cw = min(int(w * rng.uniform(0.40, 0.52)), int(h * rng.uniform(1.0, 1.15)))
        draw_car(d, int(w * rng.uniform(0.32, 0.62)), int(h * rng.uniform(0.86, 0.93)), cw, color, plate, fonts)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    arr = np.asarray(img, dtype=np.float32) + nrng.normal(0, 5, (h, w, 3))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    fs = max(11, int(h * 0.058))
    font, _ = fonts.get(fs, bold=True)
    band = int(fs * 1.6)
    od.rectangle([0, 0, w, band], fill=(0, 0, 0, 125))
    od.text((8, band // 2), c["stamps"][k], font=font, fill=(255, 226, 64, 255), anchor="lm")
    od.text((w - 8, band // 2), c["cam"], font=font, fill=(255, 255, 255, 235), anchor="rm")
    f2, _ = fonts.get(max(10, int(fs * 0.9)), bold=True)
    od.text((8, h - 6), c["overlay_loc"], font=f2, fill=(255, 255, 255, 245), anchor="ld",
            stroke_width=2, stroke_fill=(0, 0, 0, 255))
    img = Image.alpha_composite(img, ov).convert("RGB")
    return img.convert("L").convert("RGB") if gray else img


# ══════════════════ 6. 양식 3종 ══════════════════
def new_page(w, h):
    return Image.new("RGB", (w, h), PAPER)


def notes_height(pen, notes, size, width, lh):
    return sum(len(pen.wrap(n, size, width)) for n in notes) * lh


def render_A(c, fonts, rng, nrng):
    """서울시형 — 세로, 라벨|값 2열 표, 사진 2컷, 수신인 주소 블록"""
    img = new_page(W_P, H_P)
    pen = Pen(img, fonts)
    L, p, t = c["labels"], c["p"], c["traps"]
    blue = (30, 88, 160)
    emblem(pen, M + 30, 92, 30, c["emblem"], blue)
    pen.text((M + 74, 80), c["org_head"], 28, bold=True, anchor="lm")
    pen.text((M + 74, 114), f"{c['dept']} 주정차단속팀", 19, fill=GRAY, anchor="lm")
    pen.text((W_P - M, 80), f"{L['증거번호']}  {c['evid']}", 20, anchor="rm")
    for k, (lab, val) in enumerate(c["distractors"]):
        pen.text((W_P - M, 110 + 26 * k), f"{lab}  {val}", 18, fill=GRAY, anchor="rm")
    y = 150 + 26 * max(0, len(c["distractors"]) - 1)
    pen.line(M, y, W_P - M, y, fill=blue, width=3)
    y += 54
    pen.text((W_P // 2, y), c["title"], 42, bold=True, anchor="mm")
    y += 46
    if c["subtitle"]:
        pen.text((W_P // 2, y), c["subtitle"], 22, fill=GRAY, anchor="mm")
        y += 38
    pen.rect(M, y, W_P - M, y + 90, outline=LINE)
    pen.text((M + 20, y + 30), f"받는 분    {c['recipient']}", 22, bold=True, anchor="lm")
    pen.text((M + 20, y + 63), c["recipient_addr"], 19, fill=GRAY, anchor="lm")
    y = pen.para(M, y + 112, c["intro"], 21, W_P - 2 * M, line_h=33) + 14

    plate = f"{c['plate_print']} ({c['kind']})" if c["show_kind"] else c["plate_print"]
    rows = [(L["위반차량"], plate), (L["위반일시"], p["dt"]), (L["위반장소"], c["place"]),
            (L["위반내용"], c["vtext"]), (L["과태료금액"], p["amount"])]
    if "RD" in t:
        rows += [("감경액(20%)", p["reduction"]), ("감경 후 납부금액", p["reduced"])]
    else:
        rows += [(L["감경과태료"], f"{p['reduced']}  (20% 감경)")]
    if "SD" not in t:
        rows += [(L["의견진술기한"], p["deadline_cell"])]
    rows += [(L["가상계좌"], "\n".join(f"{b}  {n}" for b, n in c["accounts"]))]
    y = kv_table(pen, M, y, W_P - 2 * M, rows, 250, 22, (232, 239, 248)) + 22

    nw = W_P - 2 * M - 30
    nh = notes_height(pen, c["notes"], 17, nw, 26) + 26
    ph_h = max(170, min(320, H_P - y - nh - 256))
    ph_w = (W_P - 2 * M - 24) // 2
    for k in range(2):
        x = M + k * (ph_w + 24)
        photo = evidence_photo(ph_w, ph_h, rng, nrng, fonts, c, k, gray=c["gray_photos"])
        img.paste(photo, (x, y))
        pen.rect(x, y, x + ph_w, y + ph_h, outline=LINE)
        pen.text((x + ph_w // 2, y + ph_h + 18), f"단속사진 {k + 1}", 18, fill=GRAY, anchor="mm")
    y += ph_h + 40
    pen.rect(M, y, W_P - M, y + nh, fill=(246, 246, 243), outline=(200, 200, 200))
    yy = y + 13
    for note in c["notes"]:
        for ln in pen.wrap(note, 17, nw):
            pen.text((M + 15, yy + 13), ln, 17, fill=(60, 60, 66), anchor="lm")
            yy += 26
    signature(img, pen, fonts, rng, c, W_P // 2, y + nh + 16)
    footer(pen, W_P, H_P, c)
    return watermark(img, fonts)


def render_B(c, fonts, rng, nrng):
    """경찰서형 — 세로, 바탕체, 4칸 격자 표, 흑백 사진 1컷"""
    img = new_page(W_P, H_P)
    pen = Pen(img, fonts, serif=True)
    L, p, t = c["labels"], c["p"], c["traps"]
    emblem(pen, M + 26, 78, 26, c["emblem"], (24, 40, 88))
    pen.text((M + 64, 78), c["org_head"], 26, bold=True, anchor="lm")
    pen.text((W_P - M, 70), f"{L['증거번호']} : {c['evid']}", 20, anchor="rm")
    for k, (lab, val) in enumerate(c["distractors"]):
        pen.text((W_P - M, 98 + 26 * k), f"{lab} : {val}", 18, fill=GRAY, anchor="rm")
    y = 128 + 26 * max(0, len(c["distractors"]) - 1)
    pen.line(M, y, W_P - M, y, width=3)
    pen.line(M, y + 6, W_P - M, y + 6, width=1)
    y += 58
    pen.text((W_P // 2, y), c["title"], 44, bold=True, anchor="mm")
    y += 48
    if c["subtitle"]:
        pen.text((W_P // 2, y), c["subtitle"], 22, fill=GRAY, anchor="mm")
        y += 38
    pen.text((M, y + 14), "수  신 :  차량 소유자(사용자) 귀하", 22, anchor="lm")
    y = pen.para(M, y + 50, c["intro"], 21, W_P - 2 * M, line_h=33) + 14

    bg, LW = (236, 236, 236), 190
    VW, REST = (W_P - 2 * M - 2 * LW) // 2, W_P - 2 * M - LW
    pen.text((M, y + 16), "1. 위반 사실", 23, bold=True, anchor="lm")
    y += 38
    y = grid_row(pen, M, y, [(L["위반차량"], LW, True), (c["plate_print"], VW, False),
                              ("차  종", LW, True), (c["kind"], VW, False)], 21, bg)
    for lab, val in [(L["위반일시"], p["dt"]), (L["위반장소"], c["place"]), (L["위반내용"], c["vtext"])]:
        y = grid_row(pen, M, y, [(lab, LW, True), (val, REST, False)], 21, bg)
    if "RD" in t:
        y = grid_row(pen, M, y, [(L["과태료금액"], LW, True), (p["amount"], VW, False),
                                  ("감경액(20%)", LW, True), (p["reduction"], VW, False)], 21, bg)
        y = grid_row(pen, M, y, [("감경 후 납부금액", LW, True), (p["reduced"], REST, False)], 21, bg)
    else:
        y = grid_row(pen, M, y, [(L["과태료금액"], LW, True), (p["amount"], VW, False),
                                  (L["감경과태료"], LW, True), (p["reduced"], VW, False)], 21, bg)

    info = [] if "SD" in t else [f"○ {L['의견진술기한']} :  {p['deadline_cell']}"]
    (b0, n0), others = c["accounts"][0], c["accounts"][1:]
    info.append(f"○ {L['가상계좌']} :  {b0} {n0}")
    info += [f"      {b} {n}" for b, n in others]
    nw = W_P - 2 * M
    nh = notes_height(pen, c["notes"], 17, nw, 26)
    y += 20
    pen.text((M, y + 16), "2. 단속 사진", 23, bold=True, anchor="lm")
    y += 38
    ph_h = max(200, min(420, H_P - y - 36 - 38 - len(info) * 36 - 12 - nh - 16 - 130 - 70))
    photo = evidence_photo(nw, ph_h, rng, nrng, fonts, c, 0, gray=True)
    img.paste(photo, (M, y))
    pen.rect(M, y, W_P - M, y + ph_h, outline=LINE)
    y += ph_h + 36
    pen.text((M, y + 16), "3. 의견진술 및 납부 안내", 23, bold=True, anchor="lm")
    y += 38
    for s in info:
        pen.text((M + 4, y + 18), s, 22, anchor="lm")
        y += 36
    y += 12
    for note in c["notes"]:
        y = pen.para(M, y, note, 17, nw, line_h=26, fill=(60, 60, 66))
    signature(img, pen, fonts, rng, c, W_P // 2, y + 16)
    footer(pen, W_P, H_P, c)
    return watermark(img, fonts)


def render_C(c, fonts, rng, nrng):
    """시군 가로형 — 가로, 왼쪽 사진 4컷, 오른쪽 '라벨 위·값 아래' 격자 + 계좌표"""
    img = new_page(W_L, H_L)
    pen = Pen(img, fonts)
    L, p, t = c["labels"], c["p"], c["traps"]
    col = c["accent"]
    pen.rect(0, 0, W_L, 112, fill=col)
    emblem(pen, 78, 56, 32, c["emblem"], WHITE, ring=col)
    pen.text((124, 56), c["org_head"], 30, bold=True, fill=WHITE, anchor="lm")
    pen.text((W_L // 2, 56), c["title"], 36, bold=True, fill=WHITE, anchor="mm")
    pen.text((W_L - 60, 36), f"{L['증거번호']}  {c['evid']}", 20, fill=WHITE, anchor="rm")
    for k, (lab, val) in enumerate(c["distractors"]):
        pen.text((W_L - 60, 64 + 24 * k), f"{lab}  {val}", 17, fill=(226, 236, 232), anchor="rm")
    if c["subtitle"]:
        pen.text((60, 150), c["subtitle"], 22, fill=GRAY, anchor="lm")
    pen.text((W_L - 60, 150), f"받는 분: {c['recipient']}  ({c['recipient_addr']})", 19, fill=GRAY, anchor="rm")
    top = pen.para(60, 176, c["intro"], 20, W_L - 120, line_h=31) + 14

    lx, lw, rx = 60, 820, 910
    rw = W_L - 60 - rx
    pw, ph = (lw - 20) // 2, 272
    caps = ["전경 1", "전경 2", "번호판 1", "번호판 2"]
    for k in range(4):
        x, yy = lx + (k % 2) * (pw + 20), top + (k // 2) * (ph + 40)
        photo = evidence_photo(pw, ph, rng, nrng, fonts, c, k, closeup=k >= 2, gray=c["gray_photos"])
        img.paste(photo, (x, yy))
        pen.rect(x, yy, x + pw, yy + ph, outline=LINE)
        pen.text((x + pw // 2, yy + ph + 17), caps[k], 17, fill=GRAY, anchor="mm")
    left_end = top + 2 * (ph + 40)

    items = [(L["위반차량"], c["plate_print"], 1), (L["위반일시"], p["dt"], 1),
             (L["위반장소"], c["place"], 2), (L["위반내용"], c["vtext"], 2)]
    if "RD" in t:
        items += [(L["과태료금액"], p["amount"], 1), ("감경액(20%)", p["reduction"], 1),
                  ("감경 후 납부금액", p["reduced"], 1)]
    else:
        items += [(L["과태료금액"], p["amount"], 1), (L["감경과태료"], p["reduced"], 1)]
    if "SD" not in t:
        items += [(L["의견진술기한"], p["deadline_cell"], 1)]
    bg = (229, 241, 235)
    ry = stacked_grid(pen, rx, top, rw, items, 21, bg) + 16
    ry = account_table(pen, rx, ry, rw, L["가상계좌"], c["accounts"], 20, bg)

    y0 = max(left_end, ry) + 16
    y = y0
    for note in c["notes"]:
        y = pen.para(60, y, note, 17, 1060, line_h=25, fill=(60, 60, 66))
    signature(img, pen, fonts, rng, c, 1440, y0)
    footer(pen, W_L, H_L, c)
    return watermark(img, fonts)


RENDER = {"A": render_A, "B": render_B, "C": render_C}


# ══════════════════ 7. 휴대폰 사진처럼 열화 ══════════════════
def perspective_coeffs(dst, src):
    """PIL PERSPECTIVE 계수: 출력 좌표(dst) → 원본 좌표(src)"""
    A, B = [], []
    for (x, y), (X, Y) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -X * x, -X * y])
        B.append(X)
        A.append([0, 0, 0, x, y, 1, -Y * x, -Y * y])
        B.append(Y)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def background(w, h, rng, nrng):
    """책상·바닥 느낌의 배경"""
    base = np.array(rng.choice([(122, 88, 60), (150, 114, 80), (88, 90, 96), (204, 200, 192), (62, 64, 68)]),
                    np.float32)
    arr = np.ones((h, w, 3), np.float32) * base
    arr += nrng.normal(0, 1, (h // 6 + 1, 1, 1)).repeat(6, axis=0)[:h] * 7  # 나뭇결 같은 가로 줄무늬
    arr += nrng.normal(0, 4, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    return img.convert("RGBA")


def degrade(page, level, rng, nrng):
    if level == "clean":
        return page
    heavy = level == "heavy"
    W, H = page.size
    pg = page.copy()
    d = ImageDraw.Draw(pg)
    if heavy or rng.random() < 0.5:  # 접힌 자국
        if H > W:
            for k in (1, 2):
                yy = int(H * k / 3) + rng.randint(-10, 10)
                d.line([0, yy, W, yy], fill=(212, 210, 204), width=2)
                d.line([0, yy + 2, W, yy + 2], fill=WHITE, width=1)
        else:
            xx = W // 2 + rng.randint(-10, 10)
            d.line([xx, 0, xx, H], fill=(212, 210, 204), width=2)
    # 기울기 + 원근 (종이 네 모서리를 흔든 뒤 회전)
    mg = int(max(W, H) * (0.08 if heavy else 0.045))
    OW, OH = W + 2 * mg, H + 2 * mg
    jit = max(W, H) * (0.03 if heavy else 0.008)
    ang = math.radians(rng.uniform(-4, 4) if heavy else rng.uniform(-1.8, 1.8))
    cx, cy = OW / 2, OH / 2
    dst = []
    for x, y in [(mg, mg), (mg + W, mg), (mg + W, mg + H), (mg, mg + H)]:
        x, y = x + rng.uniform(-jit, jit), y + rng.uniform(-jit, jit)
        dst.append((cx + (x - cx) * math.cos(ang) - (y - cy) * math.sin(ang),
                    cy + (x - cx) * math.sin(ang) + (y - cy) * math.cos(ang)))
    coeffs = perspective_coeffs(dst, [(0, 0), (W, 0), (W, H), (0, H)])
    warped = pg.convert("RGBA").transform((OW, OH), PERSPECTIVE, coeffs, BICUBIC, fillcolor=(0, 0, 0, 0))
    canvas = background(OW, OH, rng, nrng)
    canvas.alpha_composite(warped)
    arr = np.asarray(canvas.convert("RGB"), dtype=np.float32)
    # 한쪽이 어두운 조명 + 색온도
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    th = rng.uniform(0, 2 * math.pi)
    g = ((xx - cx) * math.cos(th) + (yy - cy) * math.sin(th)) / (max(OW, OH) / 2)
    arr *= (1 - (0.22 if heavy else 0.10) * (g + 1) / 2)[..., None]
    arr *= np.array(rng.choice([(1.0, 0.98, 0.93), (0.97, 0.99, 1.02), (1.0, 1.0, 1.0)]), np.float32)
    if heavy:  # 손·휴대폰 그림자
        sh = Image.new("L", (OW, OH), 0)
        ex, ey = rng.uniform(-0.1, 0.4) * OW, rng.uniform(0.55, 1.05) * OH
        rx, ry = rng.uniform(0.25, 0.4) * OW, rng.uniform(0.2, 0.32) * OH
        ImageDraw.Draw(sh).ellipse([ex - rx, ey - ry, ex + rx, ey + ry], fill=255)
        sh = sh.filter(ImageFilter.GaussianBlur(OW * 0.04))
        arr *= (1 - 0.33 * np.asarray(sh, dtype=np.float32) / 255)[..., None]
    arr += nrng.normal(0, 6 if heavy else 3, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.9, 1.3) if heavy else 0.45))
    if heavy:  # 업로드 과정의 축소
        img = img.resize((int(OW * 0.9), int(OH * 0.9)), LANCZOS)
    return img


# ══════════════════ 8. 실행 ══════════════════
def contact_sheet(items, fonts, path):
    cols, tw, th, cap, gap = 5, 300, 300, 34, 14
    rows = math.ceil(len(items) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * (th + cap) + (rows + 1) * gap), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    font, _ = fonts.get(16, bold=True)
    for k, (im, label) in enumerate(items):
        thumb = im.copy()
        thumb.thumbnail((tw, th), LANCZOS)
        x, y = gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + cap + gap)
        sheet.paste(thumb, (x + (tw - thumb.width) // 2, y + (th - thumb.height) // 2))
        d.text((x + tw // 2, y + th + cap // 2), label, font=font, fill=(30, 30, 30), anchor="mm")
    sheet.save(path, quality=88)


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="한장해결AI — 과태료 사전통지서 합성 테스트셋 생성")
    ap.add_argument("--out", default="testset", help="출력 폴더 (기본 testset)")
    ap.add_argument("--seed", type=int, default=42, help="같은 seed면 같은 20장 (기본 42)")
    ap.add_argument("--base-date", default="2026-10-20", help="발행일 기준일 YYYY-MM-DD (기본 2026-10-20)")
    ap.add_argument("--save-clean", action="store_true", help="열화 전 원본 PNG도 저장")
    ap.add_argument("--font", help="고딕 .ttf/.ttc 경로")
    ap.add_argument("--font-bold", help="고딕 굵게 .ttf/.ttc 경로")
    ap.add_argument("--font-serif", help="명조·바탕 .ttf/.ttc 경로")
    ap.add_argument("--font-serif-bold", help="명조 굵게 .ttf/.ttc 경로")
    a = ap.parse_args()

    fonts = Fonts({"gothic": a.font, "gothic_bold": a.font_bold,
                   "serif": a.font_serif, "serif_bold": a.font_serif_bold})
    base = date.fromisoformat(a.base_date)
    out = Path(a.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    if a.save_clean:
        (out / "clean").mkdir(exist_ok=True)

    gt_rows, cond_rows, thumbs = [], [], []
    for i, (tpl, level, traps) in enumerate(PLAN, 1):
        rng = random.Random(f"{a.seed}-{i}")
        nrng = np.random.default_rng([a.seed, i])
        c = make_content(tpl, traps, rng, base)
        check(c)
        page = RENDER[tpl](c, fonts, rng, nrng)
        name = f"notice_{i:02d}.jpg"
        if a.save_clean:
            page.save(out / "clean" / f"notice_{i:02d}.png")
        img = degrade(page, level, rng, nrng)
        img.save(out / "images" / name, quality=QUALITY[level])

        gt_rows.append({"파일명": name, **c["gt"]})
        cond_rows.append({
            "파일명": name,
            "양식": TEMPLATES[tpl],
            "열화": LEVELS[level],
            "함정": ",".join(traps) or "-",
            "함정 설명": " / ".join(TRAPS[x] for x in traps) or "-",
            "인쇄 제목": c["title"],
            "인쇄 라벨": " ; ".join(f"{k}={v}" for k, v in c["labels_used"].items()),
            "위반일시 표기": c["p"]["dt"],
            "기한 표기": f"(문장 속) {c['dl_sentence']}" if "SD" in traps else c["p"]["deadline_cell"],
            "금액 표기": c["p"]["amount"],
            "차종": c["kind"],
            "위반유형": c["vtype"],
            "사진 속 시각": " / ".join(c["stamps"]),
        })
        thumbs.append((img, f"{i:02d} {tpl}·{LEVELS[level]} {'+'.join(traps) or '기준선'}"))
        print(f"{name}  {TEMPLATES[tpl]:<16} {LEVELS[level]:<6} {','.join(traps) or '-'}")

    write_csv(out / "ground_truth.csv", ["파일명"] + FIELDS, gt_rows)
    write_csv(out / "conditions.csv", list(cond_rows[0]), cond_rows)
    contact_sheet(thumbs, fonts, out / "contact_sheet.jpg")
    print(f"\n완료 → {out.resolve()}")
    print("  images/ 20장 · ground_truth.csv · conditions.csv · contact_sheet.jpg")


if __name__ == "__main__":
    main()
