# 🥛 Numidia Dairy Market Intelligence Pipeline

> An AI-powered dairy commodity price intelligence system built as a portfolio project for the **(Jr.) Data Engineer** role at **Numidia** — a global dairy commodity trading company headquartered in Herten, Netherlands.

---

## 🎯 What It Does

Automatically fetches **real dairy commodity prices** from the Federal Reserve's FRED API, processes them through a **Bronze → Silver → Gold medallion architecture**, generates **BUY/SELL/HOLD trading signals**, and produces **AI-powered market insights** — all in under 3 seconds.

---

## 🏗️ Architecture — Medallion Pattern

```
┌─────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER                │
│         APScheduler — runs daily at 08:00       │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│                BRONZE LAYER                     │
│   FRED API → raw JSON → raw CSV                 │
│   data/bronze/raw_dairy_prices.csv              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│                SILVER LAYER                     │
│   Clean → Validate → Quarantine Outliers        │
│   data/silver/clean_dairy_prices.csv            │
│   data/silver/quarantine.csv (audit trail)      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│                 GOLD LAYER                      │
│   Moving Averages → BUY/SELL/HOLD Signals       │
│   Price Alerts → AI Summary → SQLite DB         │
│   data/gold/market_intelligence.csv             │
└──────────┬──────────────────┬───────────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌──────────────────────────┐
│    POWER BI      │  │      STREAMLIT           │
│  Static Dashboard│  │  Interactive Dashboard   │
│  KPIs & Trends   │  │  + AI Chatbot (NL→SQL)   │
└──────────────────┘  └──────────────────────────┘
```

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Data Source | FRED API (Federal Reserve Economic Data) |
| Pipeline Language | Python 3.10 |
| Data Processing | Pandas, NumPy |
| AI Market Summary | Groq API — LLaMA 3.3-70b-versatile |
| Text-to-SQL Chatbot | Groq API — LLaMA 3.3-70b-versatile |
| Database | SQLite |
| Scheduling | APScheduler |
| Interactive Dashboard | Streamlit + Plotly |
| BI Reporting | Power BI Desktop |
| Alert Automation | Power Automate + OneDrive |
| Version Control | Git + GitHub |

---

## ✨ Key Features

### 🔴 Bronze Layer — Live Data Ingestion
- Fetches real US dairy commodity prices from FRED API
- Products: Butter, Milk, Cheese (2020 → present)
- Full audit logging with timestamps
- Raw data preserved exactly as received

### 🔵 Silver Layer — Data Quality Engine
Detects and handles 5 categories of real-world data problems:

| Issue | Detection Method | Resolution |
|---|---|---|
| Missing values | Null check | Forward fill (last known price) |
| Duplicate records | Date + product key | Keep first, remove duplicates |
| Negative prices | Value check | Forward fill |
| Malformed dates | Parse attempt | Standardize to YYYY-MM-DD |
| Statistical outliers | IQR method | **Quarantine** to separate audit file |

> **Key design decision:** Outliers are **quarantined**, not deleted. The quarantine file preserves the original values for audit traceability while keeping only verified clean data in the Gold layer.

### 🟡 Gold Layer — Market Intelligence
- **Moving averages** — 3-month and 6-month windows per product
- **Price change %** — month-on-month movement
- **Trading signals** — BUY / SELL / HOLD logic
- **Alert generation** — human-readable messages for traders
- **SQLite loading** — powers the Text-to-SQL chatbot
- **AI summary** — Groq LLaMA generates plain English market insight

### Signal Logic
```
Price dropped > 3% month-on-month   →  BUY  signal
Price rose    > 3% month-on-month   →  SELL signal
Short MA (3m) crosses above Long MA →  SELL signal
Short MA (3m) crosses below Long MA →  BUY  signal
Otherwise                            →  HOLD signal
```

### 💬 Text-to-SQL AI Chatbot
Ask questions in plain English — the system converts them to SQL, runs them against the Gold SQLite database, and returns a plain English insight.

**Example questions:**
- *"Which product had the biggest price drop last month?"*
- *"Show me all BUY signals from 2025"*
- *"What is the latest Butter price?"*

### ⏰ Automated Orchestration
Pipeline runs automatically every day at 08:00 AM via APScheduler. In production this would be deployed on Azure Functions or Windows Task Scheduler.

### 🔔 Power Automate Integration
When a BUY or SELL alert is generated, the pipeline writes a structured alert CSV to OneDrive. A Power Automate flow watches that folder and sends an email notification to the responsible trader automatically.

---

## 🚀 How to Run

### 1. Clone the repo
```bash
git clone https://github.com/Pranav14777/numidia-dairy-intelligence.git
cd numidia-dairy-intelligence
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add API keys
Create a `.env` file in the project root:
```
GROQ_API_KEY=your_groq_key_here
FRED_API_KEY=your_fred_key_here
```

Get your free FRED API key at: https://fred.stlouisfed.org/docs/api/api_key.html  
Get your free Groq API key at: https://console.groq.com

### 5. Run the full pipeline
```bash
python main.py
```

### 6. Launch the Streamlit dashboard
```bash
streamlit run dashboard.py
```

### 7. Start the automatic scheduler
```bash
python orchestrator.py
```

---

## 📁 Project Structure

```
numidia-dairy-intelligence/
│
├── fred_fetcher.py     # Bronze layer — FRED API data ingestion
├── silver_layer.py     # Silver layer — cleaning & validation
├── gold_layer.py       # Gold layer — signals, alerts, AI summary
├── main.py             # Single pipeline entry point
├── orchestrator.py     # Automated daily scheduling
├── dashboard.py        # Streamlit dashboard + AI chatbot
├── chatbot.py          # Text-to-SQL natural language interface
├── config.py           # Central configuration & settings
├── requirements.txt    # Python dependencies
├── .gitignore          # Excludes secrets and data files
│
├── data/
│   ├── bronze/         # Raw API data (gitignored)
│   ├── silver/         # Clean data + quarantine (gitignored)
│   └── gold/           # Market intelligence output (gitignored)
│
└── logs/               # Pipeline run logs (gitignored)
```

---

## 📊 Sample Pipeline Output

```
============================================================
  NUMIDIA DAIRY MARKET INTELLIGENCE PIPELINE
============================================================
  Started  : 2026-05-10 20:58:07

>>> STAGE 1 of 3 : BRONZE - Fetching live data...
    BRONZE COMPLETE - 225 records fetched

>>> STAGE 2 of 3 : SILVER - Cleaning & validating...
    Quarantined 2 outlier records
    Passing 223 CLEAN records to Gold layer
    SILVER COMPLETE - 223 clean, 0 flagged

>>> STAGE 3 of 3 : GOLD - Generating market intelligence...
    BUY signals  : 51
    SELL signals : 76
    HOLD signals : 96
    AI summary generated successfully
    GOLD COMPLETE

============================================================
  PIPELINE COMPLETE
  Duration  : 2 seconds
  Records   : 223 processed
  Alerts    : 127 sent to OneDrive
============================================================
```

---

## 🗺️ Roadmap

- [ ] Connect to GDT (Global Dairy Trade) auction API for wholesale prices
- [ ] Add PostgreSQL for production-grade data storage
- [ ] Deploy pipeline on Azure Functions for serverless scheduling
- [ ] Add year-over-year price comparison signals
- [ ] Expand to additional dairy products (WMP, SMP, AMF, Cheddar)
- [ ] Add feedback loop to improve signal accuracy over time
- [ ] Build Power Apps mobile interface for traders

---

## 👨‍💻 Built By

**Pranav Gadamsetty**  
MSc Computer Science — Eindhoven University of Technology  
Specialization: Software Engineering & Technology

[![LinkedIn](https://img.shields.io/badge/LinkedIn-pgdeveloper-blue)](https://www.linkedin.com/in/pgdeveloper/)
[![GitHub](https://img.shields.io/badge/GitHub-Pranav14777-black)](https://github.com/Pranav14777)

---

*Built as a portfolio project demonstrating Python data engineering, medallion architecture, GenAI integration, and Power Platform automation skills relevant to financial reporting and trading operations.*