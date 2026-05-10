import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from config import BRONZE_FILE, SILVER_DIR, SILVER_FILE, LOG_FILE

# ── Logging Setup ─────────────────────────────────────
os.makedirs(SILVER_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ── Validation Report ─────────────────────────────────
validation_report = {
    "total_records_in"     : 0,
    "nulls_found"          : 0,
    "nulls_fixed"          : 0,
    "duplicates_found"     : 0,
    "duplicates_removed"   : 0,
    "outliers_found"       : 0,
    "outliers_flagged"     : 0,
    "negative_prices_found": 0,
    "negative_prices_fixed": 0,
    "total_records_out"    : 0,
}


def load_bronze() -> pd.DataFrame:
    """Load raw data from Bronze layer."""
    if not os.path.exists(BRONZE_FILE):
        raise FileNotFoundError(
            f"Bronze file not found: {BRONZE_FILE}. "
            "Run fred_fetcher.py first."
        )
    df = pd.read_csv(BRONZE_FILE, parse_dates=["date"])
    logger.info(f"Loaded Bronze data - {len(df)} records")
    validation_report["total_records_in"] = len(df)
    return df


def inject_realistic_problems(df: pd.DataFrame) -> pd.DataFrame:
    """
    Intentionally introduces realistic data quality problems
    that occur in real financial data pipelines.
    This demonstrates the KIND of issues the Silver layer is
    designed to detect and fix.
    """
    logger.info("Injecting realistic data quality problems for demo...")
    df = df.copy()

    # Problem 1 - Missing values (common when API has gaps)
    df.loc[df.index[5],  "price"] = None
    df.loc[df.index[22], "price"] = None
    df.loc[df.index[48], "price"] = None

    # Problem 2 - Duplicate records (common in batch ingestion)
    duplicate_rows = df.iloc[[10, 11]].copy()
    df = pd.concat([df, duplicate_rows], ignore_index=True)

    # Problem 3 - Outlier prices (data entry error / API glitch)
    df.loc[df.index[30], "price"] = 999.99   # impossibly high
    df.loc[df.index[60], "price"] = 0.001    # impossibly low

    # Problem 4 - Negative price (should never happen)
    df.loc[df.index[15], "price"] = -2.50

    # Problem 5 - Wrong date format mixed in
    df.loc[df.index[7], "date"] = "01/15/2021"

    logger.info("  Problems injected:")
    logger.info("  - 3 missing values")
    logger.info("  - 2 duplicate rows")
    logger.info("  - 2 outlier prices")
    logger.info("  - 1 negative price")
    logger.info("  - 1 malformed date")

    return df


def fix_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize all dates to YYYY-MM-DD format."""
    logger.info("Step 1 - Standardizing date formats...")
    before = df["date"].dtype
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["date"] = df["date"].dt.normalize()  # remove time component
    logger.info(f"  Date format standardized -> YYYY-MM-DD")
    return df


def fix_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and fix missing price values.
    Strategy: forward fill within each product group.
    This is standard practice in time series financial data.
    """
    logger.info("Step 2 - Detecting and fixing missing values...")

    nulls_before = df["price"].isna().sum()
    validation_report["nulls_found"] = int(nulls_before)

    if nulls_before > 0:
        logger.info(f"  Found {nulls_before} missing price values")
        # Forward fill within each product - use last known price
        df["price"] = df.groupby("product")["price"].transform(
            lambda x: x.ffill()
        )
        # Backward fill for any remaining at start of series
        df["price"] = df.groupby("product")["price"].transform(
            lambda x: x.bfill()
        )

    nulls_after = df["price"].isna().sum()
    fixed = nulls_before - nulls_after
    validation_report["nulls_fixed"] = int(fixed)
    logger.info(f"  Fixed {fixed} missing values using forward/backward fill")
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and remove duplicate records.
    A duplicate is same product + same date.
    """
    logger.info("Step 3 - Detecting and removing duplicates...")

    before = len(df)
    validation_report["duplicates_found"] = int(
        df.duplicated(subset=["date", "product"]).sum()
    )

    df = df.drop_duplicates(subset=["date", "product"], keep="first")

    removed = before - len(df)
    validation_report["duplicates_removed"] = int(removed)
    logger.info(f"  Removed {removed} duplicate records")
    return df


def fix_negative_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and fix negative prices.
    A commodity price can never be negative in this context.
    Strategy: replace with NaN then forward fill.
    """
    logger.info("Step 4 - Detecting negative prices...")

    negative_mask = df["price"] < 0
    count = negative_mask.sum()
    validation_report["negative_prices_found"] = int(count)

    if count > 0:
        logger.info(f"  Found {count} negative price(s) - replacing with forward fill")
        df.loc[negative_mask, "price"] = None
        df["price"] = df.groupby("product")["price"].transform(
            lambda x: x.ffill()
        )

    validation_report["negative_prices_fixed"] = int(count)
    return df


def detect_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect statistical outliers using IQR method per product.
    Flags them without removing - finance teams need to know
    about unusual prices, not have them silently deleted.
    """
    logger.info("Step 5 - Detecting price outliers (IQR method)...")

    df["is_outlier"] = False
    total_outliers = 0

    for product in df["product"].unique():
        mask = df["product"] == product
        prices = df.loc[mask, "price"]

        Q1 = prices.quantile(0.25)
        Q3 = prices.quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 3 * IQR
        upper = Q3 + 3 * IQR

        outlier_mask = mask & ((df["price"] < lower) | (df["price"] > upper))
        count = outlier_mask.sum()
        df.loc[outlier_mask, "is_outlier"] = True
        total_outliers += count

        if count > 0:
            logger.info(
                f"  {product} - {count} outlier(s) flagged "
                f"[valid range: {lower:.3f} - {upper:.3f}]"
            )

    validation_report["outliers_found"]  = int(total_outliers)
    validation_report["outliers_flagged"] = int(total_outliers)
    logger.info(f"  Total outliers flagged: {total_outliers}")
    return df


def add_silver_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Add metadata columns for traceability."""
    df["price"]            = df["price"].round(4)
    df["currency"]         = "USD"
    df["unit"]             = "per lb / per gallon"
    df["source"]           = "FRED API"
    df["processed_at"]     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["data_quality"]     = df["is_outlier"].apply(
        lambda x: "FLAGGED" if x else "CLEAN"
    )
    return df


def print_validation_report():
    """Print a clean validation summary."""
    logger.info("=" * 60)
    logger.info("SILVER LAYER - VALIDATION REPORT")
    logger.info("=" * 60)
    for key, value in validation_report.items():
        label = key.replace("_", " ").title()
        logger.info(f"  {label:<30} : {value}")
    logger.info("=" * 60)


def run_silver_layer() -> pd.DataFrame:
    """
    Main Silver layer function.
    Loads Bronze data, injects problems, fixes them,
    validates, quarantines outliers, and saves only
    clean data to Silver layer for Gold processing.
    """
    logger.info("=" * 60)
    logger.info("SILVER LAYER - Starting data cleaning & validation")
    logger.info("=" * 60)

    # 1. Load raw bronze data
    df = load_bronze()

    # 2. Inject realistic problems (for demo purposes)
    df = inject_realistic_problems(df)

    # 3. Fix dates
    df = fix_dates(df)

    # 4. Fix nulls
    df = fix_nulls(df)

    # 5. Remove duplicates
    df = remove_duplicates(df)

    # 6. Fix negative prices
    df = fix_negative_prices(df)

    # 7. Detect outliers
    df = detect_outliers(df)

    # 8. Add metadata
    df = add_silver_metadata(df)

    # 9. Quarantine flagged records separately for audit
    flagged_df = df[df["data_quality"] == "FLAGGED"].copy()
    if len(flagged_df) > 0:
        quarantine_path = os.path.join(SILVER_DIR, "quarantine.csv")
        flagged_df.to_csv(quarantine_path, index=False)
        logger.info(
            f"Quarantined {len(flagged_df)} flagged outlier "
            f"records to: {quarantine_path}"
        )
        logger.info(
            f"Quarantined values: "
            f"{flagged_df[['date','product','price']].to_string(index=False)}"
        )

    # 10. Keep ONLY clean records for Gold layer
    df = df[df["data_quality"] == "CLEAN"].copy()
    logger.info(
        f"Passing {len(df)} CLEAN records to Gold layer "
        f"({len(flagged_df)} quarantined)"
    )

    # 11. Final sort
    df = df.sort_values(["product", "date"]).reset_index(drop=True)

    # 12. Save to Silver layer - CLEAN records only
    os.makedirs(SILVER_DIR, exist_ok=True)
    df.to_csv(SILVER_FILE, index=False)

    validation_report["total_records_out"] = len(df)

    # 13. Print validation report
    print_validation_report()

    logger.info(f"Clean data saved to: {SILVER_FILE}")
    logger.info("SILVER LAYER COMPLETE")

    return df


if __name__ == "__main__":
    df = run_silver_layer()
    print("\n-- Silver Layer Sample --")
    print(df.groupby("product").tail(2).to_string(index=False))
    print(f"\nTotal clean records: {len(df)}")
    print(f"Data quality breakdown:\n{df['data_quality'].value_counts()}")

