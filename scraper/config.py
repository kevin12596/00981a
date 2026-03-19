"""
00981A ETF Tracker — Configuration
"""
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "public" / "data"
LOG_DIR    = BASE_DIR / "logs"

# ── Fund info ──────────────────────────────────────────────────────────────
FUND_CODE  = "00981A"
FUND_NAME  = "主動統一台股增長"
EZ_CODE    = "49YTW"          # ezmoney 內部代碼

# ── Data sources (ordered by priority) ────────────────────────────────────
EZMONEY_URL = f"https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode={EZ_CODE}&tabName=basic"

# ── Scraper behaviour ──────────────────────────────────────────────────────
RETRY_COUNT     = 2      # per strategy
HEADLESS        = True

# ── Classification thresholds ──────────────────────────────────────────────
# Change % below this absolute value → not classified as ADD/REDUCE
MIN_CHANGE_PCT  = 0.10

# Shares change % below this → treated as CLOSE (near-zero remaining)
CLOSE_THRESHOLD = -99.0

# ── Schedule ───────────────────────────────────────────────────────────────
SCRAPE_HOUR   = 18
SCRAPE_MINUTE = 30
