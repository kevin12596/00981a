"""
00981A ETF Tracker — History Builder
Aggregates all YYYY-MM-DD.json files into history.json for the weight chart.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR

HISTORY_PATH = DATA_DIR / "history.json"


def build_history(data_dir: Path = DATA_DIR) -> dict:
    """Read all YYYY-MM-DD.json files and return a consolidated history dict."""
    files = sorted(data_dir.glob("20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))

    dates: list[str] = []
    stock_map: dict[str, dict] = {}  # code → {code, name, weights[], shares[]}

    for f in files:
        day = json.loads(f.read_text(encoding="utf-8"))
        d = day["date"]
        dates.append(d)
        idx = len(dates) - 1

        holdings_by_code = {h["code"]: h for h in day.get("holdings", [])}

        # Extend existing stocks with today's value (None if not held today)
        for code, entry in stock_map.items():
            h = holdings_by_code.get(code)
            entry["weights"].append(h["weight_pct"] if h else None)
            entry["shares"].append(h["shares"] if h else None)

        # Register newly seen stocks (backfill earlier dates with None)
        for code, h in holdings_by_code.items():
            if code not in stock_map:
                stock_map[code] = {
                    "code": code,
                    "name": h["name"],
                    "weights": [None] * idx + [h["weight_pct"]],
                    "shares":  [None] * idx + [h["shares"]],
                }

    # Sort by latest non-null weight descending
    def _latest_weight(s: dict) -> float:
        for w in reversed(s["weights"]):
            if w is not None:
                return w
        return 0.0

    stocks = sorted(stock_map.values(), key=_latest_weight, reverse=True)

    return {
        "updated": dates[-1] if dates else None,
        "dates":   dates,
        "stocks":  stocks,
    }


def save_history(data_dir: Path = DATA_DIR, out_path: Path = HISTORY_PATH) -> Path:
    history = build_history(data_dir)
    out_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = save_history()
    print(f"History saved → {path}  ({len(json.loads(path.read_text(encoding='utf-8'))['dates'])} days)")
