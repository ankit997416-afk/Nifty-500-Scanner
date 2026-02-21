import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from io import StringIO
import time
from datetime import datetime
import matplotlib  # for background_gradient
from bs4 import BeautifulSoup
import json

st.set_page_config(page_title="🦍 Ape Multibagger Hunter", layout="wide")
st.title("🦍 Ape Multibagger Hunter v2 – Now with Tickertape Scrape")
st.markdown("**Scavenger mode**: Better fundamentals from Tickertape.in (unofficial scrape) for Indian small/mid-caps. Use small lists first to avoid blocks.")

# ----------------- SIDEBAR -----------------
st.sidebar.header("Hunt Settings")
market = st.sidebar.selectbox("Market", ["NSE India 🇮🇳"], index=0)

hunt_mode = st.sidebar.radio("Hunt Mode", [
    "Quick Scan - Select Index (Yahoo fallback)",
    "Custom Tickers (Yahoo fallback)",
    "Tickertape Scrape (Better Fundamentals - Experimental)",
    "Upload Screener.in CSV (Accurate & Safe)",
    "Full NSE Scavenger (slow)"
])

# NSE index URLs (updated to archives)
index_urls = {
    "Nifty Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "Nifty Midcap 150": "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
}

@st.cache_data(ttl=3600)
def get_nse_symbols(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    df = pd.read_csv(StringIO(r.text))
    return [sym.strip() + ".NS" for sym in df.get('Symbol', pd.Series()).tolist() if sym.strip()]

# Tickertape scrape function (unofficial - based on common patterns / embedded JSON)
@st.cache_data(ttl=43200)  # cache 12 hours
def get_tickertape_data(symbol):  # symbol without .NS, e.g. 'ZOMATO'
    url = f"https://www.tickertape.in/stocks/{symbol.lower()}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return {}
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for embedded JSON data (Tickertape uses React/JSON in scripts)
        data = {}
        for script in soup.find_all('script', type='application/json'):
            try:
                json_data = json.loads(script.string)
                if isinstance(json_data, dict) and 'props' in json_data:
                    page_props = json_data['props'].get('pageProps', {})
                    overview = page_props.get('overview', {}) or {}
                    ratios = overview.get('ratios', {}) or {}
                    growth = overview.get('growth', {}) or {}
                    
                    data = {
                        'ROE %': ratios.get('roe', {}).get('value') or ratios.get('roe', None),
                        'Debt/Equity': ratios.get('debtToEquity', {}).get('value') or ratios.get('debtEquity', None),
                        'PE': ratios.get('pe', {}).get('value') or ratios.get('trailingPE', None),
                        'Market Cap Cr': overview.get('marketCap', {}).get('value') or overview.get('mcap', None),
                        'Rev Growth 5Y %': growth.get('revenueCagr5Y', {}).get('value'),
                        'Profit Growth 5Y %': growth.get('profitCagr5Y', {}).get('value'),
                        'Sector': overview.get('sector', 'N/A'),
                    }
                    # Clean numeric values
                    for k in data:
                        if isinstance(data[k], (str, float, int)):
                            try:
                                data[k] = float(str(data[k]).replace(',', '').replace('%', ''))
                            except:
                                pass
                    if data.get('ROE %') or data.get('Debt/Equity'):  # found something useful
                        return data
            except:
                pass
        
        return {}
    except Exception as e:
        st.warning(f"Tickertape scrape failed for {symbol}: {str(e)}")
        return {}

@st.cache_data(ttl=1800)
def fetch_data(tickers, use_tickertape=False):
    data = []
    progress = st.progress(0)
    for i, t in enumerate(tickers):
        progress.progress((i+1)/len(tickers))
        symbol = t.replace('.NS', '')
        try:
            if use_tickertape:
                tt = get_tickertape_data(symbol)
                time.sleep(3)  # polite delay to avoid block
                if not tt:
                    continue
                roe = tt.get('ROE %', 0)
                debt_eq = tt.get('Debt/Equity', 999)
                pe = tt.get('PE', 999)
                mcap_cr = tt.get('Market Cap Cr', 0)
                rev_g = tt.get('Rev Growth 5Y %', 0)
                eps_g = tt.get('Profit Growth 5Y %', 0)
                sector = tt.get('Sector', 'N/A')
            else:
                # Yahoo fallback
                stock = yf.Ticker(t)
                info = stock.info or {}
                roe = info.get('returnOnEquity', 0) * 100
                debt_eq = info.get('debtToEquity', 999)
                pe = info.get('trailingPE') or info.get('forwardPE', 999)
                mcap_cr = info.get('marketCap', 0) / 1e7
                rev_g = info.get('revenueGrowth', 0) * 100
                eps_g = info.get('earningsGrowth', 0) * 100
                sector = info.get('sector', 'N/A')

            # Score (adjusted for better separation)
            score = 0
            if 0 < mcap_cr < 20000: score += 5
            if roe > 18: score += 4
            if 0 <= debt_eq < 0.4: score += 4
            if 0 < pe < 22: score += 3
            if rev_g > 12: score += 2
            if eps_g > 15: score += 2

            hist = yf.Ticker(t).history(period="5y")
            cagr = 0
            if not hist.empty and len(hist) > 800:
                cagr = ((hist['Close'][-1] / hist['Close'][0]) ** (1/5) - 1) * 100

            data.append({
                'Ticker': symbol,
                'Company': info.get('longName', symbol) if not use_tickertape else symbol,
                'Mkt Cap Cr': round(mcap_cr, 1),
                'PE': round(pe, 2) if pe < 999 else None,
                'ROE %': round(roe, 1),
                'Debt/Equity': round(debt_eq, 2),
                'Rev Growth 5Y %': round(rev_g, 1),
                'Profit Growth 5Y %': round(eps_g, 1),
                '5Y CAGR %': round(cagr, 1),
                'Score': score,
                'Sector': sector,
                'Data Source': 'Tickertape' if use_tickertape else 'Yahoo'
            })
        except:
            pass

    df = pd.DataFrame(data)
    return df.sort_values('Score', ascending=False)

# ----------------- MAIN -----------------
if hunt_mode in ["Quick Scan - Select Index (Yahoo fallback)", "Tickertape Scrape (Better Fundamentals - Experimental)"]:
    chosen = st.sidebar.selectbox("Index", list(index_urls.keys()))
    use_tt = hunt_mode.startswith("Tickertape")
    btn_text = "🚀 Hunt with Tickertape!" if use_tt else "🚀 Hunt (Yahoo)"
    
    if st.sidebar.button(btn_text, type="primary"):
        tickers = get_nse_symbols(index_urls[chosen])
        st.info(f"Processing {len(tickers)} stocks...")
        results = fetch_data(tickers[:80], use_tickertape=use_tt)  # limit to avoid blocks
        if not results.empty:
            st.success(f"Found {len(results)} beasts!")
            st.dataframe(
                results.style.background_gradient(subset=['Score'], cmap='viridis'),
                height=600,
                use_container_width=True
            )
        else:
            st.error("No data – check connection or rate limits.")

elif hunt_mode == "Custom Tickers (Yahoo fallback)":
    custom = st.text_input("Tickers (comma sep)", "ZOMATO,SUZLON,IREDA,RVNL")
    if st.button("Hunt Custom"):
        tickers = [t.strip().upper() + ".NS" for t in custom.split(",") if t.strip()]
        results = fetch_data(tickers, use_tickertape=False)
        st.dataframe(results.style.background_gradient(subset=['Score'], cmap='viridis'), height=500)

elif hunt_mode == "Upload Screener.in CSV (Accurate & Safe)":
    uploaded = st.file_uploader("Upload CSV from screener.in", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        st.write(f"Loaded {len(df)} rows")
        # Add your CSV scoring logic here (as in previous version)
        st.dataframe(df.head(20))  # placeholder - expand as needed

else:
    st.warning("Full mode coming soon – too slow for now.")

st.markdown("---")
st.caption("Phase 2: Tickertape experimental scrape | Use small sets | Add time.sleep if blocked | Next: filters / alerts?")
