import os
import logging
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from groq import Groq
from config import (
    SILVER_FILE, GOLD_DIR, GOLD_FILE, ALERTS_FILE,
    SUMMARY_FILE, LOG_FILE, GROQ_API_KEY, GROQ_MODEL,
    SHORT_WINDOW, LONG_WINDOW,
    PRICE_DROP_THRESHOLD, PRICE_RISE_THRESHOLD,
    ONEDRIVE_ALERTS_PATH
)

# ── Logging Setup ─────────────────────────────────────
os.makedirs(GOLD_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_silver() -> pd.DataFrame:
    """Load clean data from Silver layer."""
    if not os.path.exists(SILVER_FILE):
        raise FileNotFoundError(
            f"Silver file not found: {SILVER_FILE}. "
            "Run silver_layer.py first."
        )
    df = pd.read_csv(SILVER_FILE, parse_dates=["date"])
    logger.info(f"Loaded Silver data - {len(df)} records")
    return df


def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate short and long moving averages per product.
    These smooth out noise and reveal the underlying price trend.
    Short window = 3 months, Long window = 6 months.
    """
    logger.info("Step 1 - Calculating moving averages...")

    df = df.sort_values(["product", "date"]).copy()

    df["ma_short"] = df.groupby("product")["price"].transform(
        lambda x: x.rolling(window=SHORT_WINDOW, min_periods=1).mean()
    )
    df["ma_long"] = df.groupby("product")["price"].transform(
        lambda x: x.rolling(window=LONG_WINDOW, min_periods=1).mean()
    )

    df["ma_short"] = df["ma_short"].round(4)
    df["ma_long"]  = df["ma_long"].round(4)

    logger.info(f"  Short MA window : {SHORT_WINDOW} periods")
    logger.info(f"  Long MA window  : {LONG_WINDOW} periods")
    return df


def calculate_price_changes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate month-on-month price change percentage per product.
    This tells traders how fast prices are moving.
    """
    logger.info("Step 2 - Calculating price change percentages...")

    df["price_change_pct"] = df.groupby("product")["price"].transform(
        lambda x: x.pct_change() * 100
    ).round(4)

    df["price_change_pct"] = df["price_change_pct"].fillna(0)
    logger.info("  Price change % calculated for all products")
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate BUY / SELL / HOLD trading signals.

    Logic:
    - BUY  : short MA crosses ABOVE long MA (price trending up - sell opportunity)
              OR price dropped more than threshold (cheap - buy opportunity)
    - SELL : short MA crosses BELOW long MA (price trending down - sell now)
              OR price rose more than threshold (peak - sell opportunity)
    - HOLD : no clear signal
    """
    logger.info("Step 3 - Generating BUY/SELL/HOLD signals...")

    def assign_signal(row):
        pct = row["price_change_pct"]
        ma_s = row["ma_short"]
        ma_l = row["ma_long"]

        # Strong price drop - good time to BUY (stock up cheap)
        if pct <= PRICE_DROP_THRESHOLD:
            return "BUY"
        # Strong price rise - good time to SELL (maximize profit)
        elif pct >= PRICE_RISE_THRESHOLD:
            return "SELL"
        # Short MA above long MA - upward momentum - consider SELL
        elif ma_s > ma_l * 1.01:
            return "SELL"
        # Short MA below long MA - downward momentum - consider BUY
        elif ma_s < ma_l * 0.99:
            return "BUY"
        else:
            return "HOLD"

    df["signal"] = df.apply(assign_signal, axis=1)

    signal_counts = df["signal"].value_counts()
    logger.info(f"  BUY signals  : {signal_counts.get('BUY', 0)}")
    logger.info(f"  SELL signals : {signal_counts.get('SELL', 0)}")
    logger.info(f"  HOLD signals : {signal_counts.get('HOLD', 0)}")
    return df


def generate_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate alerts for significant price movements.
    These are the records that would trigger a Power Automate
    notification to the trading team.
    """
    logger.info("Step 4 - Generating price alerts...")

    df["alert_flag"] = False
    df["alert_message"] = ""

    # Flag significant movements
    buy_mask  = df["signal"] == "BUY"
    sell_mask = df["signal"] == "SELL"

    df.loc[buy_mask, "alert_flag"] = True
    df.loc[buy_mask, "alert_message"] = df[buy_mask].apply(
        lambda r: (
            f"BUY ALERT: {r['product']} price is {r['price']:.3f} USD "
            f"({r['price_change_pct']:+.2f}% change). "
            f"Consider stocking up."
        ), axis=1
    )

    df.loc[sell_mask, "alert_flag"] = True
    df.loc[sell_mask, "alert_message"] = df[sell_mask].apply(
        lambda r: (
            f"SELL ALERT: {r['product']} price is {r['price']:.3f} USD "
            f"({r['price_change_pct']:+.2f}% change). "
            f"Consider selling now."
        ), axis=1
    )

    total_alerts = df["alert_flag"].sum()
    logger.info(f"  Total alerts generated: {total_alerts}")

    # Save alerts separately for Power Automate to consume
    alerts_df = df[df["alert_flag"] == True][[
        "date", "product", "price",
        "price_change_pct", "signal", "alert_message"
    ]].copy()

    alerts_df.to_csv(ALERTS_FILE, index=False)
    logger.info(f"  Alerts saved to: {ALERTS_FILE}")

    # Save to OneDrive for Power Automate trigger
    try:
        onedrive_dir = os.path.dirname(ONEDRIVE_ALERTS_PATH)
        os.makedirs(onedrive_dir, exist_ok=True)
        alerts_df.to_csv(ONEDRIVE_ALERTS_PATH, index=False)
        logger.info(f"  Alerts copied to OneDrive for Power Automate")
    except Exception as e:
        logger.warning(f"  OneDrive copy skipped: {e}")

    return df


def load_to_sqlite(df: pd.DataFrame):
    """
    Load Gold data into SQLite database.
    This enables the Text-to-SQL chatbot to query the data
    using natural language questions.
    """
    logger.info("Step 5 - Loading data into SQLite for chatbot queries...")

    db_path = os.path.join(GOLD_DIR, "dairy_intelligence.db")
    conn = sqlite3.connect(db_path)

    df.to_sql("dairy_prices", conn, if_exists="replace", index=False)

    # Verify
    count = pd.read_sql("SELECT COUNT(*) as total FROM dairy_prices", conn)
    logger.info(f"  SQLite loaded - {count['total'].values[0]} records")
    logger.info(f"  Database path: {db_path}")

    conn.close()
    return db_path


def generate_ai_summary(df: pd.DataFrame) -> str:
    """
    Use Groq LLM to generate a plain English market summary.
    This is what a trader reads in 10 seconds to understand
    the current market without opening any dashboard.
    """
    logger.info("Step 6 - Generating AI market summary via Groq...")

    # Get latest data per product for the summary
    latest = df.sort_values("date").groupby("product").last().reset_index()

    market_snapshot = ""
    for _, row in latest.iterrows():
        market_snapshot += (
            f"\n- {row['product']}: "
            f"Price = ${row['price']:.3f} USD, "
            f"Change = {row['price_change_pct']:+.2f}%, "
            f"Signal = {row['signal']}"
        )

    prompt = f"""
You are a senior dairy market analyst at Numidia, a global dairy 
commodity trading company. You provide concise, actionable market 
intelligence to traders and the CFO.

Based on the latest dairy price data:
{market_snapshot}

Write a brief market intelligence summary (4-5 sentences) that:
1. Highlights the most significant price movements
2. Identifies which products represent BUY or SELL opportunities
3. Gives a clear recommendation for the trading team
4. Uses professional but accessible language

Be direct and specific. Traders need to act on this information.
"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        summary = response.choices[0].message.content.strip()
        logger.info("  AI summary generated successfully")

    except Exception as e:
        logger.error(f"  AI summary failed: {e}")
        summary = "AI summary unavailable. Please check Groq API key."

    # Save summary
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n")
        f.write(summary)
        f.write("\n" + "=" * 60)

    logger.info(f"  Summary saved to: {SUMMARY_FILE}")
    return summary


def run_gold_layer() -> pd.DataFrame:
    """
    Main Gold layer function.
    Takes clean Silver data and produces business-ready
    market intelligence output.
    """
    logger.info("=" * 60)
    logger.info("GOLD LAYER - Starting market intelligence processing")
    logger.info("=" * 60)

    # 1. Load silver data
    df = load_silver()

    # 2. Calculate moving averages
    df = calculate_moving_averages(df)

    # 3. Calculate price changes
    df = calculate_price_changes(df)

    # 4. Generate signals
    df = generate_signals(df)

    # 5. Generate alerts
    df = generate_alerts(df)

    # 6. Save Gold layer CSV
    df.to_csv(GOLD_FILE, index=False)
    logger.info(f"Gold data saved to: {GOLD_FILE}")

    # 7. Load into SQLite for chatbot
    db_path = load_to_sqlite(df)

    # 8. Generate AI summary
    summary = generate_ai_summary(df)

    logger.info("=" * 60)
    logger.info("GOLD LAYER COMPLETE")
    logger.info("=" * 60)

    # Print results
    print("\n-- Gold Layer Sample --")
    print(df[["date", "product", "price", "price_change_pct",
              "signal", "alert_flag"]].groupby(
        "product").tail(3).to_string(index=False))

    print("\n-- Signal Summary --")
    print(df["signal"].value_counts().to_string())

    print("\n-- AI Market Summary --")
    print("-" * 60)
    print(summary)
    print("-" * 60)

    return df


if __name__ == "__main__":
    run_gold_layer()