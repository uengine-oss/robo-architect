"""Headed Playwright smoke for spec 024 mixed-mode wireframe generation.

End-to-end demo:
  1. Launch Chromium (HEADED, slow-mo so a human can follow).
  2. Open the frontend (vite dev, http://localhost:5173).
  3. Click the Figma binding button in the top menu.
  4. Inside the modal, find the "샘플 와이어프레임 생성" panel.
  5. Type a product-search brief (search bar [component] + custom list [native]
     + add-to-cart button [component]).
  6. Click "와이어프레임 생성".
  7. Wait for [data-test="sample-result"] (success line).
  8. Screenshot at each step.

Prerequisites:
  - uvicorn at 127.0.0.1:8000 launched with `--reload` (see constitution IX).
  - vite at localhost:5173.
  - Figma plugin loaded against the bound file and connected to the same
    backend (verify via `POST /api/figma-binding/components/_dev/test-render`
    returning anything other than `step: create_page_timeout`).
  - At least one component scanned for the active binding
    (`POST /api/figma-binding/components/scan` with a Figma personal-access
    token).

Run:
    ./.venv/bin/python specs/024-figma-component-aware-wireframe/tests/playwright-mixed-mode-e2e.py

Env knobs:
    RA_FRONTEND_URL   override vite URL (default http://localhost:5173)
    RA_SLOWMO_MS      per-action delay so a human can watch (default 300)

Screenshots: written to ./tmp/spec024-playwright/ relative to the repo root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


FRONTEND_URL = os.environ.get("RA_FRONTEND_URL", "http://localhost:5173")
# Resolve repo-root tmp/ regardless of where the script is invoked from
# (script lives under specs/024-.../tests/, 3 levels deep).
_REPO_ROOT = Path(__file__).resolve().parents[3]
SCREENSHOT_DIR = _REPO_ROOT / "tmp" / "spec024-playwright"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BRIEF = (
    "상품 검색 화면을 만든다. 화면 구성:\n"
    "- 상단에 검색창(placeholder: '상품명을 검색하세요')\n"
    "- 중간에 검색된 상품 목록 3건: "
    "  iPhone 15 Pro (1,550,000원), MacBook Air M3 (1,790,000원), AirPods Pro 2 (359,000원)\n"
    "- 하단에 '장바구니에 추가' 버튼\n"
    "검색창과 버튼은 기존 컴포넌트를 사용하고, 상품 목록은 네이티브 리스트로 만든다."
)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            slow_mo=int(os.environ.get("RA_SLOWMO_MS", "300")),
            args=["--window-size=1400,900"],
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        console_log: list[str] = []
        page.on("console", lambda m: console_log.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_log.append(f"[pageerror] {e}"))

        print(f"→ navigating {FRONTEND_URL}")
        page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SCREENSHOT_DIR / "01-home.png"))

        # 1. Click Figma button to open the binding modal.
        figma_btn = page.locator(".figma-btn").first
        expect(figma_btn).to_be_visible(timeout=15000)
        figma_btn.click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOT_DIR / "02-modal-open.png"))

        # 2. Wait for the sample panel to render.
        panel = page.locator('[data-test="sample-wireframe-panel"]').first
        expect(panel).to_be_visible(timeout=10000)
        panel.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        page.screenshot(path=str(SCREENSHOT_DIR / "03-panel-visible.png"))

        # 3. Replace brief + name.
        frame_name_input = page.locator('[data-test="sample-frame-name"]').first
        frame_name_input.click()
        frame_name_input.fill("상품 검색 (Playwright)")

        brief_input = page.locator('[data-test="sample-brief"]').first
        brief_input.click()
        brief_input.fill(BRIEF)
        page.wait_for_timeout(400)
        page.screenshot(path=str(SCREENSHOT_DIR / "04-brief-filled.png"))

        # 4. Click generate.
        gen_btn = page.locator('[data-test="sample-generate"]').first
        gen_btn.click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(SCREENSHOT_DIR / "05-generating.png"))

        # 5. Wait for success line (or error). Up to 3 minutes.
        try:
            result_locator = page.locator('[data-test="sample-result"]').first
            result_locator.wait_for(state="visible", timeout=180_000)
            result_text = result_locator.inner_text()
            print("✓ result:", result_text)
            page.screenshot(path=str(SCREENSHOT_DIR / "06-result.png"))
            success = True
        except Exception as e:
            print("✗ result not visible:", e)
            # Capture error if present.
            err_locator = page.locator('[data-test="sample-error"]').first
            try:
                if err_locator.is_visible():
                    print("  error text:", err_locator.inner_text())
            except Exception:
                pass
            page.screenshot(path=str(SCREENSHOT_DIR / "06-failure.png"))
            success = False

        # Linger a moment so the human watching can see the final state.
        page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOT_DIR / "07-final.png"))

        if console_log:
            print("\n--- browser console (last 20) ---")
            for line in console_log[-20:]:
                print(line)

        browser.close()
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
