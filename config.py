import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
FRED_API_KEY  = os.getenv("FRED_API_KEY")
GROQ_MODEL    = "llama-3.3-70b-versatile"

# ── Base Paths ────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
LOGS_DIR    = os.path.join(BASE_DIR, "logs")

# ── Medallion Layer Paths ─────────────────────────────
BRONZE_DIR  = os.path.join(DATA_DIR, "bronze")
SILVER_DIR  = os.path.join(DATA_DIR, "silver")
GOLD_DIR    = os.path.join(DATA_DIR, "gold")

# ── Layer File Paths ──────────────────────────────────
BRONZE_FILE = os.path.join(BRONZE_DIR, "raw_dairy_prices.csv")
SILVER_FILE = os.path.join(SILVER_DIR, "clean_dairy_prices.csv")
GOLD_FILE   = os.path.join(GOLD_DIR,   "market_intelligence.csv")
ALERTS_FILE = os.path.join(GOLD_DIR,   "alerts.csv")
SUMMARY_FILE= os.path.join(GOLD_DIR,   "ai_summary.txt")
LOG_FILE    = os.path.join(LOGS_DIR,   "pipeline.log")

# ── OneDrive Alert Trigger (for Power Automate) ───────
ONEDRIVE_ALERTS_PATH = os.path.join(
    os.path.expanduser("~"), "OneDrive", "numidia_alerts", "latest_alert.csv"
)

# ── FRED Series IDs (real dairy commodities) ──────────
FRED_SERIES = {
    "Butter"  : "APU0000FS1101",   # US Butter price
    "Milk"    : "APU0000709112",   # US Whole Milk price
    "Cheese"  : "APU0000FF1101",   # US Cheese price
}

# ── Signal Settings ───────────────────────────────────
SHORT_WINDOW          = 3     # 3-period short moving average
LONG_WINDOW           = 6     # 6-period long moving average

# ── Alert Thresholds ──────────────────────────────────
PRICE_DROP_THRESHOLD  = -3.0  # % drop  → BUY  alert
PRICE_RISE_THRESHOLD  =  3.0  # % rise  → SELL alert

# ── Pipeline Schedule ─────────────────────────────────
SCHEDULE_HOUR         = 8     # runs daily at 08:00 AM
SCHEDULE_MINUTE       = 0