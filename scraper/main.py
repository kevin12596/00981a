"""
00981A ETF Tracker — Main Entry Point
Usage: python scraper/main.py [--date YYYY-MM-DD] [--dry-run]
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent))
from config import FUND_CODE, LOG_DIR, SCRAPE_HOUR, SCRAPE_MINUTE
import scraper as scraper_mod
import comparator as comparator_mod


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "scraper.log"
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
    logger.add(log_file, level="DEBUG", rotation="1 week", retention="4 weeks",
               encoding="utf-8", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


def is_trading_day(d: date) -> bool:
    """Skip weekends (simple check — does not account for Taiwan public holidays)."""
    return d.weekday() < 5  # 0=Mon … 4=Fri


def run(target_date: str | None = None, dry_run: bool = False):
    setup_logging()

    today = date.today()
    if not is_trading_day(today):
        logger.info(f"Today ({today:%A %Y-%m-%d}) is not a trading day. Skipping.")
        return

    logger.info(f"─── 00981A ETF Tracker  •  {today.isoformat()} ───")

    # ── Step 1: Scrape ──────────────────────────────────────────────────────
    try:
        data = scraper_mod.scrape()
    except RuntimeError as e:
        logger.error(f"Scrape failed: {e}")
        sys.exit(1)

    # Check if data is actually fresh (avoid re-processing stale data)
    if data["date"] != today.isoformat():
        logger.warning(
            f"Scraped data date ({data['date']}) ≠ today ({today.isoformat()}). "
            "Data may not have been updated yet."
        )

    if not dry_run:
        scraper_mod.save(data)

    # ── Step 2: Compare ─────────────────────────────────────────────────────
    prev_day = comparator_mod.find_prev_day(data["date"])
    yesterday_data = comparator_mod.load_day(prev_day) if prev_day else None

    if yesterday_data is None:
        logger.info("No historical data found — running in snapshot mode (first run).")

    diff = comparator_mod.compare(data, yesterday_data)

    logger.info(
        f"Summary — NEW: {diff['summary']['new_positions']}, "
        f"ADD: {diff['summary']['added_positions']}, "
        f"REDUCE: {diff['summary']['reduced_positions']}, "
        f"CLOSE: {diff['summary']['closed_positions']}"
    )

    if not dry_run:
        comparator_mod.save_diff(diff)

    logger.success("Done.")
    return diff


def main():
    parser = argparse.ArgumentParser(description="00981A ETF Tracker scraper")
    parser.add_argument("--date",    help="Override target date (YYYY-MM-DD)", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Don't write output files")
    args = parser.parse_args()
    run(target_date=args.date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
