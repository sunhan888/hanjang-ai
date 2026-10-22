"""브라우저 스모크 테스트: 사진 업로드 → 판독 → 결과 → 상세 화면을 자동으로 누르고 캡처한다.

준비:  pip install -r backend/requirements-dev.txt && playwright install chromium
실행:  python scripts/smoke_e2e.py --base http://localhost:8000
       python scripts/smoke_e2e.py --base https://<배포 주소> --mock-states
--mock-states 를 주면 확인 필요·마감 당일·기한 지남·오류 화면까지 캡처한다.
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_H1 = "text=과태료 사전 안내문이에요"


async def run(base: str, image: Path, out: Path, mock_states: bool, timeout_ms: int) -> list[str]:
    from playwright.async_api import async_playwright

    out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR")
        page = await ctx.new_page()
        page.on("pageerror", lambda e: problems.append(f"페이지 오류: {e}"))

        async def shot(name: str) -> None:
            await page.screenshot(path=str(out / f"{name}.png"), full_page=True)
            print("  캡처", name)

        await page.goto(f"{base}/#/guide")
        await page.wait_for_selector("text=이렇게 찍어 주세요")
        await shot("2_guide")
        await page.goto(f"{base}/#/")
        await page.wait_for_selector("text=할 일을 알려 드려요")
        await shot("1_home")

        await page.set_input_files("#file-album", str(image))
        await page.wait_for_selector("text=이 사진으로 읽을까요?")
        await page.wait_for_timeout(500)
        await shot("3_confirm")
        await page.click("text=이 사진으로 읽기")
        await page.wait_for_selector("text=고지서를 읽고 있어요")
        await shot("4_reading")
        await page.wait_for_selector(RESULT_H1, timeout=timeout_ms)
        await page.wait_for_timeout(300)
        await shot("5_result")
        result_url = page.url

        await page.click("footer >> text=읽은 내용 전체 보기")
        await page.wait_for_selector("text=종이에서 읽은 내용")
        await shot("6_fields")
        await page.goto(result_url)
        await page.wait_for_selector(RESULT_H1)
        await page.click("text=왜 그런지 법에서 확인하기")
        await page.wait_for_selector("text=왜 그런지 법으로 보기")
        await shot("7_law")
        await page.goto(result_url)
        await page.wait_for_selector(RESULT_H1)
        link = page.locator("text=내는 방법 보기")
        if await link.count():
            await link.first.click()
            await page.wait_for_selector("text=할 일 자세히")
            await shot("8_todo")

        if mock_states:
            mid = "00000000-0000-4000-8000-000000000001"
            for kind, wait in (("check", "칸을 확인해 주세요"), ("today", "오늘이 마감일이에요"), ("overdue", "기한이 지났어요")):
                await page.goto(f"{base}/?mock={kind}#/result/{mid}")
                await page.wait_for_selector(f"text={wait}", timeout=10000)
                await page.wait_for_timeout(300)
                await shot(f"9_mock_{kind}")
            for code, name in (("UNREADABLE?reason=cut", "cut"), ("UNSUPPORTED", "unsupported")):
                await page.goto(f"{base}/#/error/{code}")
                await page.wait_for_selector("h1")
                await shot(f"9_error_{name}")
        await browser.close()
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--image", default=str(ROOT / "eval" / "testset" / "images" / "notice_06.jpg"))
    ap.add_argument("--out", default=str(ROOT / "scripts" / "shots"))
    ap.add_argument("--mock-states", action="store_true")
    ap.add_argument("--timeout", type=int, default=60, help="판독을 기다릴 최대 초")
    a = ap.parse_args()
    problems = asyncio.run(run(a.base.rstrip("/"), Path(a.image), Path(a.out), a.mock_states, a.timeout * 1000))
    if problems:
        print("\n문제가 있어요:\n- " + "\n- ".join(problems))
        sys.exit(1)
    print(f"\n통과. 캡처: {a.out}")


if __name__ == "__main__":
    main()
