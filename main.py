import logging
import sys
from datetime import datetime
from config import LOG_FILE
from fred_fetcher import fetch_dairy_prices
from silver_layer import run_silver_layer
from gold_layer import run_gold_layer

# ── Logging Setup ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_pipeline():
    """
    Master pipeline runner.
    Executes all three layers in sequence:
    Bronze -> Silver -> Gold

    This is the single entry point for the entire
    Numidia Dairy Market Intelligence pipeline.
    """

    start_time = datetime.now()

    print("\n")
    print("=" * 60)
    print("  NUMIDIA DAIRY MARKET INTELLIGENCE PIPELINE")
    print("=" * 60)
    print(f"  Started  : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\n")

    # ── BRONZE LAYER ──────────────────────────────────
    print(">>> STAGE 1 of 3 : BRONZE - Fetching live data...")
    print("-" * 60)
    try:
        bronze_df = fetch_dairy_prices()
        print(f"    BRONZE COMPLETE - {len(bronze_df)} records fetched\n")
    except Exception as e:
        logger.error(f"BRONZE LAYER FAILED: {e}")
        print(f"    BRONZE FAILED: {e}")
        sys.exit(1)

    # ── SILVER LAYER ──────────────────────────────────
    print(">>> STAGE 2 of 3 : SILVER - Cleaning & validating...")
    print("-" * 60)
    try:
        silver_df = run_silver_layer()
        clean_count = len(silver_df[silver_df["data_quality"] == "CLEAN"])
        flag_count  = len(silver_df[silver_df["data_quality"] == "FLAGGED"])
        print(f"    SILVER COMPLETE - {clean_count} clean, {flag_count} flagged\n")
    except Exception as e:
        logger.error(f"SILVER LAYER FAILED: {e}")
        print(f"    SILVER FAILED: {e}")
        sys.exit(1)

    # ── GOLD LAYER ────────────────────────────────────
    print(">>> STAGE 3 of 3 : GOLD - Generating market intelligence...")
    print("-" * 60)
    try:
        gold_df = run_gold_layer()
        buy_count  = len(gold_df[gold_df["signal"] == "BUY"])
        sell_count = len(gold_df[gold_df["signal"] == "SELL"])
        hold_count = len(gold_df[gold_df["signal"] == "HOLD"])
        alert_count = gold_df["alert_flag"].sum()
        print(f"    GOLD COMPLETE - BUY:{buy_count} SELL:{sell_count} HOLD:{hold_count}\n")
    except Exception as e:
        logger.error(f"GOLD LAYER FAILED: {e}")
        print(f"    GOLD FAILED: {e}")
        sys.exit(1)

    # ── PIPELINE COMPLETE ─────────────────────────────
    end_time  = datetime.now()
    duration  = (end_time - start_time).seconds

    print("\n")
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Finished  : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Duration  : {duration} seconds")
    print(f"  Records   : {len(gold_df)} processed")
    print(f"  Signals   : {buy_count} BUY / {sell_count} SELL / {hold_count} HOLD")
    print(f"  Alerts    : {int(alert_count)} sent to OneDrive")
    print("=" * 60)
    print("\n  Outputs ready:")
    print("  - Gold CSV    : data/gold/market_intelligence.csv")
    print("  - Alerts CSV  : data/gold/alerts.csv")
    print("  - AI Summary  : data/gold/ai_summary.txt")
    print("  - SQLite DB   : data/gold/dairy_intelligence.db")
    print("  - OneDrive    : numidia_alerts/latest_alert.csv")
    print("  - Log         : logs/pipeline.log")
    print("=" * 60)
    print("\n")

    return gold_df


if __name__ == "__main__":
    run_pipeline()