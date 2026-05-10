import os
import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
from datetime import datetime
from config import (
    GOLD_FILE, ALERTS_FILE, SUMMARY_FILE,
    GROQ_API_KEY, GROQ_MODEL,
    GOLD_DIR
)

# ── Page Config ───────────────────────────────────────
st.set_page_config(
    page_title="Numidia Dairy Intelligence",
    page_icon="🥛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e2130, #252b40);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2d3555;
        text-align: center;
    }
    .buy-signal  { color: #00e676; font-weight: bold; }
    .sell-signal { color: #ff5252; font-weight: bold; }
    .hold-signal { color: #ffab40; font-weight: bold; }
    .header-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
    }
    .subheader {
        color: #8892b0;
        font-size: 0.95rem;
        margin-bottom: 20px;
    }
    .stChatMessage { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)


# ── Data Loading ──────────────────────────────────────
@st.cache_data
def load_gold_data():
    if not os.path.exists(GOLD_FILE):
        return pd.DataFrame()
    df = pd.read_csv(GOLD_FILE, parse_dates=["date"])
    return df


@st.cache_data
def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return pd.DataFrame()
    return pd.read_csv(ALERTS_FILE, parse_dates=["date"])


def load_ai_summary():
    if not os.path.exists(SUMMARY_FILE):
        return "AI summary not yet generated. Run the pipeline first."
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        return f.read()


def get_db_connection():
    db_path = os.path.join(GOLD_DIR, "dairy_intelligence.db")
    if not os.path.exists(db_path):
        return None
    return sqlite3.connect(db_path)


# ── Text to SQL Chatbot ───────────────────────────────
def run_text_to_sql(question: str) -> str:
    """
    Converts natural language question to SQL,
    runs it against the Gold SQLite database,
    and returns a plain English insight.
    """
    conn = get_db_connection()
    if conn is None:
        return "Database not found. Please run the pipeline first."

    # Step 1 - Get table schema
    schema = pd.read_sql(
        "PRAGMA table_info(dairy_prices)", conn
    )["name"].tolist()

    # Step 2 - Convert question to SQL using Groq
    client = Groq(api_key=GROQ_API_KEY)

    sql_prompt = f"""
You are a SQL expert. Convert the user's question into a 
valid SQLite SQL query.

Table name: dairy_prices
Columns: {', '.join(schema)}

Key column values:
- product: 'Butter', 'Milk', 'Cheese'
- signal: 'BUY', 'SELL', 'HOLD'
- data_quality: 'CLEAN', 'FLAGGED'
- alert_flag: 0 or 1
- price: numeric (USD)
- price_change_pct: numeric (percentage)
- date: YYYY-MM-DD format

Rules:
- Return ONLY the SQL query
- No explanations, no markdown, no backticks
- Use proper SQLite syntax
- Always include LIMIT 20 unless asking for counts

User question: {question}
"""

    try:
        sql_response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": sql_prompt}],
            max_tokens=200,
            temperature=0.1
        )
        sql_query = sql_response.choices[0].message.content.strip()
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

        # Step 3 - Run SQL query
        result_df = pd.read_sql(sql_query, conn)
        conn.close()

        if result_df.empty:
            return "No data found for that query."

        # Step 4 - Convert result to plain English insight
        insight_prompt = f"""
You are a senior dairy market analyst at Numidia, a global 
dairy commodity trading company.

The trader asked: "{question}"

The data returned:
{result_df.to_string(index=False)}

Write a clear, concise answer in 2-3 sentences.
Be specific with numbers. Use professional but accessible language.
Focus on what this means for trading decisions.
"""

        insight_response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": insight_prompt}],
            max_tokens=200,
            temperature=0.3
        )

        insight = insight_response.choices[0].message.content.strip()

        # Return both the SQL and insight for transparency
        return f"{insight}\n\n*SQL: `{sql_query}`*"

    except Exception as e:
        conn.close() if conn else None
        return f"Query failed: {str(e)}"


# ── Sidebar ───────────────────────────────────────────
def render_sidebar(df):
    st.sidebar.image(
        "https://numidiadairy.com/wp-content/uploads/2021/03/logo.png",
        width=180
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Pipeline Controls")

    if st.sidebar.button("Run Pipeline Now", type="primary"):
        with st.spinner("Running full pipeline..."):
            try:
                from main import run_pipeline
                run_pipeline()
                st.cache_data.clear()
                st.sidebar.success("Pipeline complete!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Pipeline failed: {e}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filters")

    products = ["All"] + sorted(df["product"].unique().tolist())
    selected_product = st.sidebar.selectbox("Product", products)

    signals = ["All", "BUY", "SELL", "HOLD"]
    selected_signal = st.sidebar.selectbox("Signal", signals)

    date_range = st.sidebar.date_input(
        "Date Range",
        value=[df["date"].min(), df["date"].max()],
        min_value=df["date"].min(),
        max_value=df["date"].max()
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.markdown("""
    **Numidia Dairy Intelligence**
    
    Built by Pranav Gadamsetty
    
    Stack: Python, FRED API,
    Medallion Architecture,
    Groq LLaMA, SQLite,
    Streamlit, Power BI
    """)

    return selected_product, selected_signal, date_range


# ── KPI Cards ─────────────────────────────────────────
def render_kpis(df, alerts_df):
    col1, col2, col3, col4, col5 = st.columns(5)

    latest = df.sort_values("date").groupby("product").last()

    with col1:
        st.metric(
            label="Total Records",
            value=f"{len(df):,}",
            delta="Processed"
        )
    with col2:
        buy_count = len(df[df["signal"] == "BUY"])
        st.metric(
            label="BUY Signals",
            value=buy_count,
            delta="Active opportunities"
        )
    with col3:
        sell_count = len(df[df["signal"] == "SELL"])
        st.metric(
            label="SELL Signals",
            value=sell_count,
            delta="Take profit signals"
        )
    with col4:
        alert_count = len(alerts_df)
        st.metric(
            label="Total Alerts",
            value=alert_count,
            delta="Sent to traders"
        )
    with col5:
        flagged = len(df[df["data_quality"] == "FLAGGED"])
        st.metric(
            label="Flagged Records",
            value=flagged,
            delta="Quality issues"
        )


# ── Price Chart ───────────────────────────────────────
def render_price_chart(df):
    st.subheader("Dairy Price Trends with Moving Averages")

    products = df["product"].unique()
    fig = go.Figure()

    colors = {
        "Butter": "#4fc3f7",
        "Milk":   "#81c784",
        "Cheese": "#ffb74d"
    }

    for product in products:
        pdata = df[df["product"] == product].sort_values("date")
        color = colors.get(product, "#ffffff")

        # Actual price line
        fig.add_trace(go.Scatter(
            x=pdata["date"],
            y=pdata["price"],
            name=f"{product} Price",
            line=dict(color=color, width=2),
            mode="lines"
        ))

        # Short MA
        fig.add_trace(go.Scatter(
            x=pdata["date"],
            y=pdata["ma_short"],
            name=f"{product} MA({3})",
            line=dict(color=color, width=1, dash="dot"),
            opacity=0.6
        ))

        # Long MA
        fig.add_trace(go.Scatter(
            x=pdata["date"],
            y=pdata["ma_long"],
            name=f"{product} MA({6})",
            line=dict(color=color, width=1, dash="dash"),
            opacity=0.4
        ))

    fig.update_layout(
        template="plotly_dark",
        height=450,
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)


# ── Signal Chart ──────────────────────────────────────
def render_signal_chart(df):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Signal Distribution")
        signal_counts = df["signal"].value_counts().reset_index()
        signal_counts.columns = ["Signal", "Count"]

        colors_map = {
            "BUY": "#00e676",
            "SELL": "#ff5252",
            "HOLD": "#ffab40"
        }

        fig = px.bar(
            signal_counts,
            x="Signal",
            y="Count",
            color="Signal",
            color_discrete_map=colors_map,
            template="plotly_dark"
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Price Change % by Product")
        latest = df.sort_values("date").groupby(
            "product"
        ).last().reset_index()

        fig = px.bar(
            latest,
            x="product",
            y="price_change_pct",
            color="signal",
            color_discrete_map={
                "BUY": "#00e676",
                "SELL": "#ff5252",
                "HOLD": "#ffab40"
            },
            template="plotly_dark",
            text="price_change_pct"
        )
        fig.update_traces(texttemplate="%{text:.2f}%")
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# ── Alerts Table ──────────────────────────────────────
def render_alerts(alerts_df):
    st.subheader("Active Trading Alerts")

    if alerts_df.empty:
        st.info("No alerts generated yet. Run the pipeline first.")
        return

    latest_alerts = alerts_df.sort_values(
        "date", ascending=False
    ).head(10)

    for _, row in latest_alerts.iterrows():
        signal = row["signal"]
        color = "🟢" if signal == "BUY" else "🔴"
        with st.expander(
            f"{color} {signal} — {row['product']} | "
            f"${row['price']:.3f} | "
            f"{row['price_change_pct']:+.2f}% | "
            f"{row['date'].strftime('%Y-%m-%d')}"
        ):
            st.write(row["alert_message"])


# ── AI Summary ────────────────────────────────────────
def render_ai_summary():
    st.subheader("AI Market Intelligence Summary")

    summary = load_ai_summary()

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1a2744, #1e3a5f);
        border-radius: 12px;
        padding: 24px;
        border-left: 4px solid #4fc3f7;
        color: #e0e0e0;
        font-size: 1rem;
        line-height: 1.8;
    ">
    {summary}
    </div>
    """, unsafe_allow_html=True)


# ── AI Chatbot ────────────────────────────────────────
def render_chatbot():
    st.subheader("Ask the Data — Natural Language Queries")
    st.markdown(
        "Ask any question about the dairy market data in plain English."
    )

    # Example questions
    st.markdown("**Example questions:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Which product has the most BUY signals?"):
            st.session_state.messages.append({
                "role": "user",
                "content": "Which product has the most BUY signals?"
            })
    with col2:
        if st.button("What is the latest Butter price?"):
            st.session_state.messages.append({
                "role": "user",
                "content": "What is the latest Butter price?"
            })
    with col3:
        if st.button("Show me all SELL alerts from 2025"):
            st.session_state.messages.append({
                "role": "user",
                "content": "Show me all SELL alerts from 2025"
            })

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input(
        "Ask a question about dairy prices..."
    ):
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analysing data..."):
                response = run_text_to_sql(prompt)
            st.markdown(response)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })


# ── Data Table ────────────────────────────────────────
def render_data_table(df):
    st.subheader("Full Market Intelligence Data")

    display_cols = [
        "date", "product", "price",
        "price_change_pct", "ma_short",
        "ma_long", "signal", "data_quality"
    ]

    st.dataframe(
        df[display_cols].sort_values(
            ["date"], ascending=False
        ),
        use_container_width=True,
        height=300
    )


# ── Main App ──────────────────────────────────────────
def main():
    # Header
    st.markdown(
        '<p class="header-title">Numidia Dairy Market Intelligence</p>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<p class="subheader">Real-time dairy commodity price '
        'analysis, trading signals, and AI-powered market insights</p>',
        unsafe_allow_html=True
    )
    st.markdown("---")

    # Load data
    df = load_gold_data()
    alerts_df = load_alerts()

    if df.empty:
        st.error(
            "No data found. Please run the pipeline first: "
            "`python main.py`"
        )
        return

    # Sidebar filters
    selected_product, selected_signal, date_range = render_sidebar(df)

    # Apply filters
    filtered_df = df.copy()
    if selected_product != "All":
        filtered_df = filtered_df[
            filtered_df["product"] == selected_product
        ]
    if selected_signal != "All":
        filtered_df = filtered_df[
            filtered_df["signal"] == selected_signal
        ]
    if len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df["date"] >= pd.Timestamp(date_range[0])) &
            (filtered_df["date"] <= pd.Timestamp(date_range[1]))
        ]

    # Render sections
    render_kpis(df, alerts_df)
    st.markdown("---")
    render_price_chart(filtered_df)
    st.markdown("---")
    render_signal_chart(filtered_df)
    st.markdown("---")

    # Two column layout for alerts and AI summary
    col1, col2 = st.columns([1, 1])
    with col1:
        render_alerts(alerts_df)
    with col2:
        render_ai_summary()

    st.markdown("---")
    render_chatbot()
    st.markdown("---")
    render_data_table(filtered_df)


if __name__ == "__main__":
    main()