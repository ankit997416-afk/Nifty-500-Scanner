import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")

# ─── STYLE ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.big-title {font-size:36px; font-weight:700; margin-bottom:8px;}
.good {color:#22c55e; font-weight:600;}
.warn  {color:#eab308; font-weight:600;}
.bad   {color:#ef4444; font-weight:600;}
.metric-label {font-size:14px !important;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">📈 Smart Stock Analyzer</div>', unsafe_allow_html=True)
st.caption("Technical Trend • Fundamentals • Risk • NSE Scanner")

# ─── SIDEBAR CONTROLS ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    w_tech = st.slider("Technical weight",  0.0, 1.0, 0.45, step=0.05)
    w_fund = st.slider("Fundamental weight",0.0, 1.0, 0.35, step=0.05)
    w_risk = st.slider("Risk weight",        0.0, 1.0, 0.20, step=0.05)
    
    st.header("📊 Data")
    price_period = st.selectbox("Price history", ["1y","2y","3y","5y"], index=1)
    scan_size_default = 20

# ─── DATA FETCHERS (cached) ───────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_price(symbol, period="2y"):
    try:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if len(df) >= 40:
            return df
    except:
        pass
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except:
        return {}

@st.cache_data(ttl=86400, show_spinner=False)
def get_financials(symbol):
    try:
        t = yf.Ticker(symbol)
        bs = t.balance_sheet
        cf = t.cashflow
        if bs.empty or cf.empty:
            return None, None
        return bs, cf
    except:
        return None, None

@st.cache_data(ttl=86400 * 2, show_spinner=False)
def get_nse_index(index_name):
    url = f"https://www.nseindia.com/api/equity-stockIndices?index={index_name}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }
    try:
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=headers, timeout=6)
        resp = s.get(url, headers=headers, timeout=6)
        data = resp.json()
        return [item['symbol'] + ".NS" for item in data.get('data', [])]
    except:
        return []

# ─── SCORING LOGIC ────────────────────────────────────────────────────────
def technical_score(df):
    if df is None or len(df) < 40:
        return 0, ["Insufficient price data"]

    score = 0
    reasons = []

    df['SMA50']  = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()

    latest = df.iloc[-1]

    if latest['Close'] > latest['SMA50']:
        score += 1
    else:
        reasons.append("Below 50 SMA")

    if latest['SMA50'] > latest['SMA200']:
        score += 1
    else:
        reasons.append("50 SMA < 200 SMA")

    # Simple RSI(14)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    if rsi.iloc[-1] > 50:
        score += 1
    else:
        reasons.append("RSI ≤ 50")

    return min(score, 3), reasons

def fundamental_score(info):
    score = 0
    reasons = []

    if info.get("returnOnEquity", 0) > 0.15:
        score += 1
    else:
        reasons.append("ROE ≤ 15%")

    if info.get("revenueGrowth", 0) > 0.10:
        score += 1
    else:
        reasons.append("Revenue growth weak")

    pe = info.get("trailingPE", 999)
    if pe < 32 and pe > 0:
        score += 1
    else:
        reasons.append("PE too high / unavailable")

    return score, reasons

def risk_score(bs, cf):
    score = 0
    reasons = []

    try:
        if bs is not None and not bs.empty:
            latest = bs.iloc[:, 0]
            equity = latest.get("Total Stockholder Equity", 0)
            ppe    = latest.get("Property Plant And Equipment", latest.get("Property Plant Equipment", 0))
            if equity > ppe * 1.15:
                score += 1
            else:
                reasons.append("High fixed assets vs equity")

        if cf is not None and not cf.empty:
            latest_cf = cf.iloc[:, 0]
            op_cf = latest_cf.get("Total Cash From Operating Activities",
                                  latest_cf.get("Net Cash Provided By Operating Activities", 0))
            if op_cf > 0:
                score += 1
            else:
                reasons.append("Negative operating CF")
    except:
        reasons.append("Financials unavailable")

    return score, reasons

def overall_probability(t, f, r, w_tech, w_fund, w_risk):
    max_raw = 3 * w_tech + 3 * w_fund + 2 * w_risk   # rough max possible
    raw = t * w_tech + f * w_fund + r * w_risk
    pct = (raw / max_raw) * 100 if max_raw > 0 else 10
    return int(min(max(pct, 10), 95))

# ─── CORE ANALYZE FUNCTION ────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def analyze(symbol, period):
    df   = load_price(symbol, period)
    if df is None:
        return None

    info = get_info(symbol)
    bs, cf = get_financials(symbol)

    t, tr = technical_score(df)
    f, fr = fundamental_score(info)
    r, rr = risk_score(bs, cf)

    prob = overall_probability(t, f, r, w_tech, w_fund, w_risk)

    return {
        "Symbol": symbol,
        "Prob": prob,
        "Tech": t,
        "Fund": f,
        "Risk": r,
        "Reasons": ", ".join(tr + fr + rr) or "—",
        "Price": round(info.get("currentPrice", np.nan), 2),
        "Sector": info.get("sector", "—"),
        "df": df
    }

# ─── PLOT FUNCTION ────────────────────────────────────────────────────────
def plot_price(df, symbol):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Close', line=dict(color='#22c55e')))
    if 'SMA50'  in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'],  name='50 SMA',  line=dict(color='#3b82f6', dash='dash')))
    if 'SMA200' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], name='200 SMA', line=dict(color='#8b5cf6', dash='dot')))
    fig.update_layout(
        title=f"{symbol}  —  Price & Moving Averages",
        template="plotly_dark",
        height=520,
        xaxis_title="",
        yaxis_title="Price (₹)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    st.plotly_chart(fig, use_container_width=True)

# ─── LAYOUT ───────────────────────────────────────────────────────────────
tab_single, tab_scan = st.tabs(["🔍 Single Stock", "📊 Category Scanner"])

# ─── SINGLE STOCK ─────────────────────────────────────────────────────────
with tab_single:
    st.subheader("Single Stock Analysis")
    col1, col2 = st.columns([3,1])
    with col1:
        raw_sym = st.text_input("NSE Symbol", value="TCS.NS", help="Example: RELIANCE.NS, HDFCBANK.NS")
    symbol = raw_sym.strip().upper()
    if not (symbol.endswith(".NS") or symbol.endswith(".BO")):
        symbol += ".NS"

    if symbol:
        with st.spinner("Analyzing..."):
            result = analyze(symbol, price_period)
        
        if result:
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Technical", result["Tech"])
            c2.metric("Fundamental", result["Fund"])
            c3.metric("Risk", result["Risk"])
            c4.metric("Probability", f"{result['Prob']}%")

            st.progress(result["Prob"] / 100)

            if result["Prob"] >= 75:
                st.markdown('<p class="good">Strong Candidate</p>', unsafe_allow_html=True)
            elif result["Prob"] >= 55:
                st.markdown('<p class="warn">Potential – Watch</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="bad">High Risk / Avoid</p>', unsafe_allow_html=True)

            if result["Reasons"] != "—":
                st.caption("**Flags / Weaknesses**")
                st.write(result["Reasons"])

            plot_price(result["df"], symbol)

# ─── SCANNER ──────────────────────────────────────────────────────────────
with tab_scan:
    st.subheader("Market Category Scanner")

    cat = st.selectbox("Category", ["NIFTY 100", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250"], index=0)

    scan_size = st.slider("Stocks to scan", 5, 60, scan_size_default)

    if st.button(f"🚀 Scan {cat} (top {scan_size})", type="primary"):
        with st.spinner("Fetching index constituents..."):
            if cat == "NIFTY 100":
                STOCK_LIST = get_nse_index("NIFTY 100")
            elif cat == "NIFTY MIDCAP 150":
                STOCK_LIST = get_nse_index("NIFTY MIDCAP 150")
            else:
                STOCK_LIST = get_nse_index("NIFTY SMALLCAP 250")

        if not STOCK_LIST:
            st.error("Could not load NSE index. Check internet or try later.")
        else:
            selected = STOCK_LIST[:scan_size]
            results = []
            progress = st.progress(0)

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(analyze, s, price_period): s for s in selected}
                for i, future in enumerate(as_completed(futures)):
                    res = future.result()
                    if res:
                        results.append(res)
                    progress.progress((i + 1) / len(selected))

            if results:
                df = pd.DataFrame(results).drop(columns=["df"]).sort_values("Prob", ascending=False)
                st.dataframe(
                    df[["Symbol", "Prob", "Tech", "Fund", "Risk", "Price", "Sector", "Reasons"]],
                    use_container_width=True,
                    hide_index=True
                )

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"scanner_{cat.replace(' ','_')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No valid results. Some symbols may have missing data.")

st.caption("Data from Yahoo Finance & NSE • Not financial advice • For learning & exploration only")
