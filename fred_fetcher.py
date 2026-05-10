import os
import logging
import pandas as pd
from fredapi import Fred
from datetime import datetime
from config import FRED_API_KEY, FRED_SERIES, BRONZE_DIR, BRONZE_FILE, LOG_FILE

# ── Logging Setup ─────────────────────────────────────
os.makedirs(BRONZE_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def fetch_dairy_prices() -> pd.DataFrame:
    """
    Fetches real dairy commodity price data from FRED API.
    Returns a combined DataFrame with all products.
    Saves raw data to Bronze layer.
    """
    logger.info("=" * 60)
    logger.info("BRONZE LAYER - Starting data fetch from FRED API")
    logger.info("=" * 60)

    fred = Fred(api_key=FRED_API_KEY)
    all_series = []

    for product, series_id in FRED_SERIES.items():
        try:
            logger.info(f"Fetching {product} -> Series ID: {series_id}")
            series = fred.get_series(
                series_id,
                observation_start="2020-01-01",
                observation_end=datetime.today().strftime("%Y-%m-%d")
            )

            df = series.reset_index()
            df.columns = ["date", "price"]
            df["product"]   = product
            df["series_id"] = series_id
            df["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            all_series.append(df)
            logger.info(f"  OK {product} - {len(df)} records fetched")

        except Exception as e:
            logger.error(f"  FAILED Failed to fetch {product}: {e}")
            continue

    if not all_series:
        logger.error("No data fetched. Check your FRED API key and series IDs.")
        return pd.DataFrame()

    # Combine all products into one DataFrame
    combined = pd.concat(all_series, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.sort_values(["product", "date"]).reset_index(drop=True)

    # Save to Bronze layer - raw, untouched
    os.makedirs(BRONZE_DIR, exist_ok=True)
    combined.to_csv(BRONZE_FILE, index=False)

    logger.info("-" * 60)
    logger.info(f"BRONZE LAYER COMPLETE")
    logger.info(f"Total records : {len(combined)}")
    logger.info(f"Products      : {combined['product'].unique().tolist()}")
    logger.info(f"Date range    : {combined['date'].min()} -> {combined['date'].max()}")
    logger.info(f"Saved to      : {BRONZE_FILE}")
    logger.info("=" * 60)

    return combined


if __name__ == "__main__":
    df = fetch_dairy_prices()
    print("\n── Bronze Layer Sample ──")
    print(df.groupby("product").tail(3).to_string(index=False))