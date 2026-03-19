"""
00981A ETF Tracker — Scraper
Strategy:
  1. Intercept XHR/fetch responses from ezmoney → grab holdings JSON directly
  2. Fallback: regex-based text extraction from rendered page HTML
  3. Fallback: MOPS (公開資訊觀測站) via requests (no Playwright needed)
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DATA_DIR, FUND_CODE, FUND_NAME, EZ_CODE,
    RETRY_COUNT, HEADLESS
)

RETRY_DELAY_SHORT = 30   # seconds between retries (shorter for CI)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_num(text: str) -> float | None:
    t = re.sub(r"[,\s%　]", "", str(text).strip())
    if not t or t in ("-", "—", "N/A", ""):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _make_result(holdings: list[dict], nav=None, fund_size=None) -> dict:
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


def _is_tw_stock_code(code: str) -> bool:
    """4–6 alphanumeric starting with digit, e.g. 2330, 00981A, 0050."""
    return bool(re.match(r"^\d{4,6}[A-Za-z]?$", str(code).strip()))


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: Intercept ezmoney XHR / fetch responses
# ─────────────────────────────────────────────────────────────────────────────

def _parse_intercepted(responses: list) -> list[dict]:
    """
    Walk all intercepted JSON payloads looking for an array of holdings.
    Handles various shape variations from ezmoney internal APIs.
    """
    candidates = []

    def _walk(obj, depth=0):
        if depth > 6:
            return
        if isinstance(obj, list) and len(obj) >= 5:
            # Check if elements look like stock holdings
            sample = obj[0] if obj else {}
            if isinstance(sample, dict):
                keys = {k.lower() for k in sample}
                has_code   = any(k in keys for k in ("code","stockcode","股票代號","股票代碼","證券代號","id"))
                has_share  = any(k in keys for k in ("shares","share","持有股數","持股數","數量","qty"))
                has_weight = any(k in keys for k in ("weight","pct","percent","比例","持股比例","權重","ratio"))
                if has_code or (has_share and has_weight):
                    candidates.append(obj)
        if isinstance(obj, dict):
            for v in obj.values():
                _walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, depth + 1)

    for payload in responses:
        _walk(payload)

    if not candidates:
        return []

    # Take the largest candidate list
    best = max(candidates, key=len)
    holdings = []
    for item in best:
        if not isinstance(item, dict):
            continue
        # Try to normalise the fields
        code   = _find_field(item, ["code","stockcode","股票代號","股票代碼","證券代號","id","stkno"])
        name   = _find_field(item, ["name","stockname","股票名稱","名稱","stkname","short"])
        shares = _find_field(item, ["shares","share","持有股數","持股數","數量","qty","volume"])
        weight = _find_field(item, ["weight","pct","percent","比例","持股比例","權重","ratio","rate"])

        if code is None:
            continue
        code = str(code).strip()
        if not _is_tw_stock_code(code):
            continue

        shares_val = _clean_num(shares) if shares is not None else None
        weight_val = _clean_num(weight) if weight is not None else None

        if shares_val is None and weight_val is None:
            continue

        holdings.append({
            "code":       code,
            "name":       str(name).strip() if name else "",
            "shares":     int(shares_val) if shares_val is not None else 0,
            "weight_pct": round(weight_val, 2) if weight_val is not None else 0.0,
        })

    return holdings


def _find_field(d: dict, keys: list[str]):
    for k in d:
        if k.lower() in [kw.lower() for kw in keys]:
            return d[k]
    return None


def scrape_ezmoney_xhr() -> dict | None:
    """Load ezmoney page with Playwright, intercept all XHR/fetch responses."""
    url = f"https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode={EZ_CODE}&tabName=basic"

    intercepted_json = []
    nav = None
    fund_size = None

    def handle_response(response):
        nonlocal nav, fund_size
        ctype = response.headers.get("content-type", "")
        if "json" not in ctype:
            return
        try:
            body = response.json()
            intercepted_json.append(body)
            # Try to grab nav / fund_size from the intercepted data
            _try_extract_meta(body)
        except Exception:
            pass

    def _try_extract_meta(obj, depth=0):
        nonlocal nav, fund_size
        if depth > 4 or not isinstance(obj, dict):
            return
        for k, v in obj.items():
            kl = k.lower()
            if "nav" in kl or "淨值" in kl:
                n = _clean_num(v)
                if n and nav is None:
                    nav = n
            if "size" in kl or "規模" in kl or "aum" in kl:
                n = _clean_num(v)
                if n and fund_size is None:
                    fund_size = round(n / 1e8, 2) if n > 1e6 else n
            _try_extract_meta(v, depth + 1)

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
        page.on("response", handle_response)

        try:
            page.goto(url, timeout=30_000, wait_until="networkidle")
            # Give JS a bit more time to finish async calls
            page.wait_for_timeout(3000)
        except PWTimeout:
            logger.warning("[ezmoney-xhr] Page load timeout — checking intercepted data anyway")
        finally:
            # Save debug HTML for inspection
            try:
                html = page.content()
                debug_path = DATA_DIR / "_debug_ezmoney.html"
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                debug_path.write_text(html, encoding="utf-8")
                logger.debug(f"[ezmoney-xhr] Debug HTML saved → {debug_path}")

                # Fallback: also try text-based extraction from rendered HTML
                text_holdings = _extract_from_text(html)
            except Exception:
                text_holdings = []
            browser.close()

    logger.info(f"[ezmoney-xhr] Intercepted {len(intercepted_json)} JSON responses")

    # Try XHR-based parse first
    holdings = _parse_intercepted(intercepted_json)
    if holdings:
        logger.success(f"[ezmoney-xhr] Found {len(holdings)} holdings via XHR interception")
        return _make_result(holdings, nav, fund_size)

    # Fall back to text extraction
    if text_holdings:
        logger.success(f"[ezmoney-xhr] Found {len(text_holdings)} holdings via text extraction")
        return _make_result(text_holdings, nav, fund_size)

    logger.warning("[ezmoney-xhr] Could not extract holdings from ezmoney")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: Text-based extraction from rendered HTML
# ─────────────────────────────────────────────────────────────────────────────

def _extract_from_text(html: str) -> list[dict]:
    """
    Regex sweep across ALL text in the page.
    Looks for patterns matching Taiwan stock codes next to share counts / weights.
    Works even if data is in <div> or <span> layout instead of <table>.
    """
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n")

    # Pattern: stock code (4-6 digit) followed by name, shares, weight on nearby lines
    code_re   = re.compile(r"^(\d{4,6}[A-Za-z]?)$")
    num_re    = re.compile(r"^[\d,]+$")
    weight_re = re.compile(r"^(\d{1,3}\.\d{1,4})%?$")

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    holdings = []
    i = 0
    while i < len(lines):
        m = code_re.match(lines[i])
        if m and _is_tw_stock_code(m.group(1)):
            code = m.group(1)
            # Look ahead up to 6 lines for name, shares, weight
            window = lines[i+1:i+8]
            name   = next((l for l in window if re.search(r"[\u4e00-\u9fff]", l) and len(l) <= 20), "")
            shares_str = next((l for l in window if num_re.match(l.replace(",", "")) and len(l) >= 4), None)
            weight_str = next((l for l in window if weight_re.match(l.rstrip("%"))), None)

            shares = int(shares_str.replace(",", "")) if shares_str else 0
            weight = float(weight_re.match(weight_str.rstrip("%")).group(1)) if weight_str else 0.0

            if shares > 0 or weight > 0:
                holdings.append({
                    "code":       code,
                    "name":       name,
                    "shares":     shares,
                    "weight_pct": round(weight, 2),
                })
        i += 1

    # Deduplicate by code
    seen = {}
    for h in holdings:
        seen[h["code"]] = h
    return list(seen.values())


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: MOPS (公開資訊觀測站) via requests
# ─────────────────────────────────────────────────────────────────────────────

def scrape_mops() -> dict | None:
    """
    Fetch ETF holdings from MOPS (mops.twse.com.tw).
    Uses simple HTTP requests — no Playwright needed.
    Note: MOPS data may be T-1 or monthly for active ETFs.
    """
    if requests is None or BeautifulSoup is None:
        return None

    url = "https://mops.twse.com.tw/mops/web/ajax_t68sb12"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://mops.twse.com.tw/mops/web/t68sb12",
    }
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK": "all",
        "isnew": "false",
        "fund_id": FUND_CODE.replace("A", ""),   # MOPS might use numeric code
    }

    try:
        r = requests.post(url, data=payload, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        holdings = _parse_mops_table(soup)
        if holdings:
            logger.success(f"[mops] Found {len(holdings)} holdings")
            return _make_result(holdings)
    except Exception as e:
        logger.error(f"[mops] {e}")
    return None


def _parse_mops_table(soup) -> list[dict]:
    holdings = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not any("代" in h or "股" in h for h in headers):
            continue
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 3:
                continue
            code   = cells[0]
            name   = cells[1] if len(cells) > 1 else ""
            shares = _clean_num(cells[2]) if len(cells) > 2 else None
            weight = _clean_num(cells[3]) if len(cells) > 3 else None
            if _is_tw_stock_code(code) and shares:
                holdings.append({
                    "code":       code,
                    "name":       name,
                    "shares":     int(shares),
                    "weight_pct": round(weight, 2) if weight else 0.0,
                })
    return holdings


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def scrape() -> dict:
    """Try all strategies in order; raise RuntimeError if all fail."""
    strategies = [
        ("ezmoney-xhr", scrape_ezmoney_xhr),
        ("mops",        scrape_mops),
    ]

    for name, fn in strategies:
        for attempt in range(1, RETRY_COUNT + 1):
            logger.info(f"[{name}] Attempt {attempt}/{RETRY_COUNT}")
            try:
                result = fn()
                if result and result.get("holdings"):
                    return result
                logger.warning(f"[{name}] Returned 0 holdings")
            except Exception as e:
                logger.error(f"[{name}] Exception: {e}")

            if attempt < RETRY_COUNT:
                logger.info(f"Retrying in {RETRY_DELAY_SHORT}s…")
                time.sleep(RETRY_DELAY_SHORT)

    raise RuntimeError("All scrape strategies failed.")


def save(data: dict) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{data['date']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Saved → {path}")
    return path


if __name__ == "__main__":
    data = scrape()
    save(data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
