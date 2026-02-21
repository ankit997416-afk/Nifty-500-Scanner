import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from io import StringIO
import matplotlib  # <-- explicitly imported so background_gradient works

st.set_page_config(page_title="🦍 Ape Multibagger Hunter", layout="wide")
st.title("🦍 Ape Multibagger Hunter")
st.markdown("**Literally a scavenger hunting 10x–100x beasts** — Small/Mid-cap, high growth, low debt, fat FCF, still cheap. Built for the tribe.")

# ----------------- SIDEBAR -----------------
st.sidebar.header("Hunt Settings")
market = st.sidebar.selectbox("Market", ["NSE India 🇮🇳"], index=0)

hunt_mode = st.sidebar.radio("Hunt Mode", [
    "Quick Scan - Select Index",
    "Custom Tickers (comma separated)",
    "Full NSE Scavenger (slow but savage)"
])

# NSE index CSVs (official sources)
index_urls = {
    "Nifty Smallcap 250 (prime hunting ground)": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "Nifty Midcap 150": "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "Nifty 50 (for comparison only)": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
}

@st.cache_data(ttl=3600)
def get_nse_symbols(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"Failed to fetch index list: {r.status_code}")
        return []
    df = pd.read_csv(StringIO(r.text))
    if 'Symbol' not in df.columns:
        st.error("CSV format changed - no 'Symbol' column found")
        return []
    return [sym.strip() + ".NS" for sym in df['Symbol'].tolist() if isinstance(sym, str) and sym.strip()]

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_multibagger_data(tickers):
    data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, t in enumerate(tickers):
        status_text.text(f"Scanning {i+1}/{len(tickers)} → {t}")
        try:
            stock = yf.Ticker(t)
            info = stock.info or {}
            hist_5y = stock.history(period="5y", auto_adjust=True)

            mcap_cr = info.get('marketCap', 0) / 1e7 if info.get('marketCap') else 0
            pe = info.get('trailingPE') or info.get('forwardPE')
            roe = info.get('returnOnEquity', 0) * 100
            debt_eq = info.get('debtToEquity', 0)
            rev_growth = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') is not None else 0
            eps_growth = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') is not None else 0
            profit_margin = info.get('profitMargins', 0) * 100
            fcf = info.get('freeCashflow', 0)
            fcf_yield = (fcf / info.get('marketCap', 1)) * 100 if info.get('marketCap') and fcf else 0

            cagr = 0
            if not hist_5y.empty and len(hist_5y) >= 1000:  # roughly 4–5 years of trading days
                cagr = ((hist_5y['Close'][-1] / hist_5y['Close'][0]) ** (1/5) - 1) * 100

            # Multibagger Score (max 20)
            score = 0
            if mcap_cr < 20000: score += 4
            if roe > 15: score += 3
            if debt_eq < 0.5: score += 3
            if rev_growth > 15: score += 3
            if eps_growth > 20: score += 3
            if pe and pe < 25: score += 2
            if profit_margin > 10: score += 1
            if fcf_yield > 5: score += 1

            data.append({
                'Ticker': t.replace('.NS', ''),
                'Company': info.get('longName', t),
                'Mkt Cap (₹ Cr)': round(mcap_cr, 1),
                'PE': round(pe, 2) if pe else None,
                'ROE %': round(roe, 1),
                'Debt/Equity': round(debt_eq, 2),
                'Rev Growth %': round(rev_growth, 1),
                'EPS Growth %': round(eps_growth, 1),
                '5Y CAGR %': round(cagr, 1),
                'FCF Yield %': round(fcf_yield, 1),
                'Score': score,
                'Sector': info.get('sector', 'N/A')
            })
        except Exception:
            pass  # silent skip bad tickers

        progress_bar.progress((i + 1) / len(tickers))

    status_text.empty()
    df = pd.DataFrame(data)
    return df.sort_values('Score', ascending=False)

# ----------------- MAIN HUNT LOGIC -----------------
if hunt_mode == "Quick Scan - Select Index":
    chosen_index = st.sidebar.selectbox("Choose hunting ground", list(index_urls.keys()))
    if st.sidebar.button("🚀 START THE HUNT", type="primary"):
        with st.spinner("Fetching index constituents..."):
            tickers = get_nse_symbols(index_urls[chosen_index])
        if not tickers:
            st.stop()
        st.info(f"Scavenging {len(tickers)} stocks from {chosen_index}...")
        results = fetch_multibagger_data(tickers[:300])  # cap for reasonable speed
        st.success(f"Hunt complete! Found {len(results)} usable beasts 🦍")
        if not results.empty:
            st.dataframe(
                results.style.background_gradient(subset=['Score'], cmap='viridis'),
                height=650,
                use_container_width=True
            )
        else:
            st.warning("No data returned — possible Yahoo Finance rate limit or bad tickers.")

elif hunt_mode == "Custom Tickers (comma separated)":
    custom_input = st.text_input("Enter tickers (comma separated)", "ZOMATO,RVNL,IREDA,SUZLON,KALYANKJIL")
    if st.button("Hunt these beasts"):
        tickers = [t.strip().upper() + ".NS" for t in custom_input.split(",") if t.strip()]
        if tickers:
            results = fetch_multibagger_data(tickers)
            if not results.empty:
                st.dataframe(
                    results.style.background_gradient(subset=['Score'], cmap='viridis'),
                    height=500
                )
            else:
                st.warning("No valid data found for these tickers.")

else:  # Full NSE Scavenger
    st.warning("⚠️ This mode scans hundreds of stocks → takes 8–15 minutes. Use only if you're patient.")
    if st.button("I AM READY — FULL SCAVENGER MODE"):
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        with st.spinner("Downloading full NSE list..."):
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                df_nse = pd.read_csv(StringIO(r.text))
                tickers = [sym.strip() + ".NS" for sym in df_nse['SYMBOL'].tolist() if isinstance(sym, str)]
                st.info(f"Starting full hunt on {len(tickers)} stocks...")
                results = fetch_multibagger_data(tickers[:600])  # safety cap
                st.dataframe(
                    results.style.background_gradient(subset=['Score'], cmap='viridis'),
                    height=650
                )
            else:
                st.error("Could not download full NSE list.")

st.markdown("---")
st.caption("🛠️ Phase 1 | Built by the tribe | Next: filters, backtest, alerts, Grok commentary?")
