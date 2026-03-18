"""
00981A ETF Tracker — Scraper
Fetches holdings from ezmoney (primary) or uni-psg (fallback).
Requires: playwright, beautifulsoup4
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# Playwright import guard
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DATA_DIR, FUND_CODE, FUND_NAME, SOURCES,
    RETRY_COUNT, RETRY_DELAY_SEC, HEADLESS
)

# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_number(text: str) -> float | None:
    """Remove commas/spaces/% and cast to float; return None on failure."""
    t = re.sub(r"[,\s%]", "", text.strip())
    if not t or t in ("-", "—", "N/A"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _parse_ezmoney(html: str) -> dict | None:
    """
    Parse the ezmoney ETF detail page.
    Returns a holdings dict matching the spec JSON schema, or None on failure.
    """
    soup = BeautifulSoup(html, "lxml")
    holdings = []

    # ── Fund metadata ──────────────────────────────────────────────────────
    nav = None
    fund_size = None

    # Try to find NAV / fund size from info blocks
    for span in soup.find_all(string=re.compile(r"淨值|基金規模|資產規模")):
        parent = span.parent
        if parent:
            # Grab the next sibling / text that looks like a number
            sibling = parent.find_next_sibling()
            if sibling:
                val = _clean_number(sibling.get_text())
                if val is not None:
                    text_lower = str(span).lower()
                    if "淨值" in text_lower and nav is None:
                        nav = val
                    elif ("規模" in text_lower or "資產" in text_lower) and fund_size is None:
                        fund_size = val

    # ── Holdings table ─────────────────────────────────────────────────────
    # ezmoney renders a table with columns: 股票代碼, 股票名稱, 持有股數, 持股比例
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        # Find the right table by checking for expected column keywords
        has_code  = any("代碼" in h or "股票" in h for h in headers)
        has_share = any("股數" in h or "持有" in h for h in headers)
        if not (has_code and has_share):
            continue

        # Map column indices
        col_code   = _find_col(headers, ["代碼", "股票代碼"])
        col_name   = _find_col(headers, ["名稱", "股票名稱"])
        col_shares = _find_col(headers, ["股數", "持有股數"])
        col_weight = _find_col(headers, ["比例", "持股比例", "權重"])

        if col_code is None or col_shares is None:
            continue

        for tr in table.find_all("tr")[1:]:  # skip header
            cells = tr.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            code   = cells[col_code].get_text(strip=True) if col_code < len(cells) else ""
            name   = cells[col_name].get_text(strip=True) if col_name is not None and col_name < len(cells) else ""
            shares = _clean_number(cells[col_shares].get_text()) if col_shares < len(cells) else None
            weight = _clean_number(cells[col_weight].get_text()) if col_weight is not None and col_weight < len(cells) else None

            # Basic sanity check: stock code should be 4-6 digits
            if not re.match(r"^\d{4,6}[A-Z]?$", code):
                continue
            if shares is None:
                continue

            holdings.append({
                "code":        code,
                "name":        name,
                "shares":      int(shares),
                "weight_pct":  round(weight, 2) if weight is not None else 0.0,
            })

        if holdings:
            break

    if not holdings:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "date":               today,
        "fund_code":          FUND_CODE,
        "fund_name":          FUND_NAME,
        "nav":                nav,
        "fund_size_billion":  fund_size,
        "total_stocks":       len(holdings),
        "scrape_time":        datetime.now().isoformat(timespec="seconds"),
        "holdings":           holdings,
    }


def _find_col(headers: list[str], keywords: list[str]) -> int | None:
    for i, h in enumerate(headers):
        for kw in keywords:
            if kw in h:
                return i
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Browser fetch
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_with_playwright(url: str, wait_selector: str, timeout_ms: int) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-TW",
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
            html = page.content()
        finally:
            browser.close()
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def scrape() -> dict:
    """
    Try each data source in priority order.
    Returns the parsed holdings dict or raises RuntimeError on total failure.
    """
    import time

    for source_name, cfg in SOURCES.items():
        for attempt in range(1, RETRY_COUNT + 1):
            logger.info(f"[{source_name}] Attempt {attempt}/{RETRY_COUNT} → {cfg['url']}")
            try:
                html = _fetch_with_playwright(
                    cfg["url"], cfg["wait_selector"], cfg["timeout_ms"]
                )
                result = _parse_ezmoney(html)
                if result and result["holdings"]:
                    logger.success(
                        f"[{source_name}] Scraped {len(result['holdings'])} holdings"
                    )
                    return result
                else:
                    logger.warning(f"[{source_name}] Parsed 0 holdings — page structure may have changed")
            except PWTimeout:
                logger.warning(f"[{source_name}] Timeout on attempt {attempt}")
            except Exception as exc:
                logger.error(f"[{source_name}] Error: {exc}")

            if attempt < RETRY_COUNT:
                logger.info(f"Waiting {RETRY_DELAY_SEC}s before retry…")
                time.sleep(RETRY_DELAY_SEC)

    raise RuntimeError("All scrape sources failed. Check logs for details.")


def save(data: dict) -> Path:
    """Save scraped data as YYYY-MM-DD.json and return the path."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{data['date']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Saved → {path}")
    return path


if __name__ == "__main__":
    import time
    data = scrape()
    save(data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
