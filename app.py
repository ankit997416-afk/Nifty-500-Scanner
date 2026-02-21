import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from io import StringIO
from datetime import datetime

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

# NSE index CSVs (official, always fresh)
index_urls = {
    "Nifty Smallcap 250 (prime hunting ground)": "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "Nifty Midcap 150": "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Nifty Next 50": "https://nsearchives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "Nifty 50 (for comparison only)": "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"
}

@st.cache_data(ttl=3600)
def get_nse_symbols(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    df = pd.read_csv(StringIO(r.text))
    return [sym + ".NS" for sym in df['Symbol'].tolist()]

@st.cache_data(ttl=1800)
def fetch_multibagger_data(tickers):
    data = []
    progress_bar = st.progress(0)
    for i, t in enumerate(tickers):
        try:
            stock = yf.Ticker(t)
            info = stock.info
            hist_5y = stock.history(period="5y")
            
            # Basic metrics
            mcap_cr = info.get('marketCap', 0) / 1e7 if info.get('marketCap') else 0
            pe = info.get('trailingPE') or info.get('forwardPE')
            roe = info.get('returnOnEquity', 0) * 100
            debt_eq = info.get('debtToEquity', 0)
            rev_growth = info.get('revenueGrowth', 0) * 100
            eps_growth = info.get('earningsGrowth', 0) * 100
            profit_margin = info.get('profitMargins', 0) * 100
            fcf_yield = info.get('freeCashflow', 0) / info.get('marketCap', 1) * 100 if info.get('marketCap') else 0
            
            # 5-year CAGR
            if not hist_5y.empty and len(hist_5y) > 250:
                cagr = ((hist_5y['Close'][-1] / hist_5y['Close'][0]) ** (1/5) - 1) * 100
            else:
                cagr = 0
            
            # Multibagger Score (0-20)
            score = 0
            if mcap_cr < 20000: score += 4          # small/mid = higher upside
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
        except:
            pass
        progress_bar.progress((i+1)/len(tickers))
    
    df = pd.DataFrame(data)
    return df.sort_values('Score', ascending=False)

# ----------------- MAIN HUNT -----------------
if hunt_mode == "Quick Scan - Select Index":
    chosen_index = st.sidebar.selectbox("Choose hunting ground", list(index_urls.keys()))
    if st.sidebar.button("🚀 START THE HUNT", type="primary"):
        tickers = get_nse_symbols(index_urls[chosen_index])
        st.info(f"Scavenging {len(tickers)} stocks from {chosen_index}...")
        results = fetch_multibagger_data(tickers[:250])  # cap for speed
        st.success("Hunt complete! Here are the freshest kills 🦍")
        st.dataframe(results.style.background_gradient(subset=['Score'], cmap='viridis'), height=600)

elif hunt_mode == "Custom Tickers (comma separated)":
    custom = st.text_input("Enter tickers (e.g. ZOMATO, RVNL, IREDA, SUZLON)", "ZOMATO,RVNL,IREDA,SUZLON,KALYANIJEW")
    if st.button("Hunt these beasts"):
        tickers = [t.strip().upper() + ".NS" for t in custom.split(",")]
        results = fetch_multibagger_data(tickers)
        st.dataframe(results)

else:  # Full NSE
    st.warning("⚠️ This will take 5–10 minutes. Only true hunters proceed.")
    if st.button("I AM READY — FULL SCAVENGER MODE"):
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers)
        df_nse = pd.read_csv(StringIO(r.text))
        tickers = [sym + ".NS" for sym in df_nse['SYMBOL'].tolist()]
        results = fetch_multibagger_data(tickers[:500])  # first 500 for sanity
        st.dataframe(results)

# Click any row → detailed view (expand later in journey)
st.markdown("---")
st.caption("Built by the tribe with ❤️ & stone tools | Next phase: backtesting, AI Grok scoring, alerts, portfolio tracker?")
