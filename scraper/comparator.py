"""
00981A ETF Tracker — Comparator
Compares today's holdings against yesterday's and produces a diff JSON.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR, MIN_CHANGE_PCT, CLOSE_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Load helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_day(day: str) -> dict | None:
    """Load data/YYYY-MM-DD.json; return None if not found."""
    path = DATA_DIR / f"{day}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_prev_day(today: str, lookback: int = 10) -> str | None:
    """
    Walk backwards up to `lookback` days to find the most recent
    existing data file (skips weekends automatically).
    """
    d = date.fromisoformat(today)
    for _ in range(lookback):
        d -= timedelta(days=1)
        if (DATA_DIR / f"{d.isoformat()}.json").exists():
            return d.isoformat()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────────────

def _classify(
    code: str,
    today_shares: int,
    yesterday_shares: int,
) -> str:
    """Return action label: NEW | ADD | REDUCE | CLOSE | UNCHANGED."""
    if yesterday_shares == 0 and today_shares > 0:
        return "NEW"
    if today_shares == 0:
        return "CLOSE"

    change_pct = ((today_shares - yesterday_shares) / yesterday_shares) * 100

    if change_pct <= CLOSE_THRESHOLD:
        return "CLOSE"
    if change_pct > MIN_CHANGE_PCT:
        return "ADD"
    if change_pct < -MIN_CHANGE_PCT:
        return "REDUCE"
    return "UNCHANGED"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compare(today_data: dict, yesterday_data: dict | None) -> dict:
    """
    Build the diff dict between today and yesterday.
    If yesterday_data is None (first-run), all holdings are marked UNCHANGED.
    """
    today_holdings    = {h["code"]: h for h in today_data.get("holdings", [])}
    yesterday_holdings: dict = {}
    if yesterday_data:
        yesterday_holdings = {h["code"]: h for h in yesterday_data.get("holdings", [])}

    all_codes = set(today_holdings) | set(yesterday_holdings)

    changes   = []
    unchanged = []

    for code in sorted(all_codes):
        t = today_holdings.get(code)
        y = yesterday_holdings.get(code)

        today_shares     = t["shares"]     if t else 0
        yesterday_shares = y["shares"]     if y else 0
        today_weight     = t["weight_pct"] if t else 0.0
        yesterday_weight = y["weight_pct"] if y else 0.0
        name             = (t or y)["name"]

        if yesterday_data is None:
            # First run — no comparison possible
            unchanged.append({
                "code":       code,
                "name":       name,
                "shares":     today_shares,
                "weight_pct": today_weight,
            })
            continue

        action = _classify(code, today_shares, yesterday_shares)

        if action == "UNCHANGED":
            unchanged.append({
                "code":       code,
                "name":       name,
                "shares":     today_shares,
                "weight_pct": today_weight,
            })
        else:
            shares_change = today_shares - yesterday_shares
            if yesterday_shares > 0:
                shares_change_pct = round((shares_change / yesterday_shares) * 100, 2)
            else:
                shares_change_pct = None

            changes.append({
                "code":               code,
                "name":               name,
                "action":             action,
                "shares_today":       today_shares,
                "shares_yesterday":   yesterday_shares,
                "shares_change":      shares_change,
                "shares_change_pct":  shares_change_pct,
                "weight_today":       round(today_weight, 2),
                "weight_yesterday":   round(yesterday_weight, 2),
                "weight_change":      round(today_weight - yesterday_weight, 2),
            })

    # Sort changes: NEW first, then ADD (by weight desc), REDUCE, CLOSE
    order = {"NEW": 0, "ADD": 1, "REDUCE": 2, "CLOSE": 3}
    changes.sort(key=lambda r: (order.get(r["action"], 9), -abs(r.get("weight_change", 0))))

    summary = {
        "new_positions":     sum(1 for c in changes if c["action"] == "NEW"),
        "added_positions":   sum(1 for c in changes if c["action"] == "ADD"),
        "reduced_positions": sum(1 for c in changes if c["action"] == "REDUCE"),
        "closed_positions":  sum(1 for c in changes if c["action"] == "CLOSE"),
    }

    yesterday_size = yesterday_data.get("fund_size_billion") if yesterday_data else None
    today_size     = today_data.get("fund_size_billion")
    size_change    = None
    if today_size and yesterday_size:
        size_change = round(((today_size - yesterday_size) / yesterday_size) * 100, 2)

    return {
        "date":                   today_data["date"],
        "prev_date":              yesterday_data["date"] if yesterday_data else None,
        "fund_size_today":        today_size,
        "fund_size_yesterday":    yesterday_size,
        "fund_size_change_pct":   size_change,
        "nav":                    today_data.get("nav"),
        "total_stocks":           today_data.get("total_stocks"),
        "scrape_time":            today_data.get("scrape_time"),
        "summary":                summary,
        "changes":                changes,
        "unchanged":              unchanged,
    }


def save_diff(diff: dict) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "latest_diff.json"
    path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Diff saved → {path}")
    return path


if __name__ == "__main__":
    from datetime import date as Date
    today = Date.today().isoformat()
    today_data = load_day(today)
    if not today_data:
        logger.error(f"No data for today ({today}). Run scraper first.")
        sys.exit(1)
    prev = find_prev_day(today)
    yesterday_data = load_day(prev) if prev else None
    diff = compare(today_data, yesterday_data)
    print(json.dumps(diff, ensure_ascii=False, indent=2))
