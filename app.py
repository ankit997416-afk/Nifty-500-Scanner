import streamlit as st
import pandas as pd
import requests
import time
from io import StringIO

st.set_page_config(page_title="🦍 Multibagger Hunter", layout="wide")
st.title("🦍 Multibagger Hunter – NSE Focus")
st.markdown("Hunt for potential 10x+ stocks: High ROE, low debt, growth at reasonable price. Data from Financial Modeling Prep (free tier).")

# Input API key (for testing; in production use st.secrets)
FMP_API_KEY = st.text_input("Enter your FMP API key (free from financialmodelingprep.com)", type="password")

if not FMP_API_KEY:
    st.info("Enter your key above to start hunting.")
    st.stop()

# Current working NSE index CSV URLs (as of 2026)
SMALLCAP_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
MIDCAP_URL   = "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv"

@st.cache_data(ttl=86400)  # cache 1 day
def get_nse_tickers():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    def load_index(url):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            if 'Symbol' not in df.columns:
                st.warning(f"No 'Symbol' column found in {url}")
                return []
            symbols = df['Symbol'].dropna().astype(str).str.strip().str.upper().tolist()
            return symbols
        except Exception as e:
            st.warning(f"Failed to load index from {url}: {str(e)}")
            return []
    
    small_symbols = load_index(SMALLCAP_URL)
    mid_symbols   = load_index(MIDCAP_URL)
    
    all_symbols = small_symbols + mid_symbols
    tickers = [s + ".NS" for s in all_symbols if s]
    
    if not tickers:
        # Fallback hardcoded list if URLs fail
        st.warning("Index fetch failed → using small fallback list for testing.")
        tickers = [
            "ZOMATO.NS", "SUZLON.NS", "IREDA.NS", "RVNL.NS", "KPITTECH.NS", "MCX.NS",
            "LAURUSLABS.NS", "HINDCOPPER.NS", "NAVINFLUOR.NS", "RADICO.NS", "CDSL.NS",
            "DELHIVERY.NS", "JWL.NS", "KAYNES.NS", "ANGELONE.NS", "POLYCAB.NS"
        ]
    
    st.info(f"Loaded {len(tickers)} potential tickers.")
    return tickers

tickers = get_nse_tickers()

@st.cache_data(ttl=86400 * 7)  # cache fundamentals 1 week
def fetch_fmp_fundamentals(symbol):
    try:
        url = f"https://financialmodelingprep.com/api/v3/ratios/{symbol}?apikey={FMP_API_KEY}&limit=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        if not isinstance(data, list) or not data:
            return {}
        latest = data[0]
        return {
            'Ticker': symbol.replace('.NS', ''),
            'MarketCapCr': (latest.get('marketCap', 0) or 0) / 1e7,
            'ROE': (latest.get('returnOnEquityTTM', 0) or 0) * 100,
            'Debt/Equity': latest.get('debtEquityRatioTTM', 999),
            'PE': latest.get('priceEarningsRatio', 999),
            'RevenueGrowth': (latest.get('revenueGrowthTTM', 0) or 0) * 100,
            'NetProfitMargin': (latest.get('netProfitMarginTTM', 0) or 0) * 100,
        }
    except Exception as e:
        # Silent fail for individual stocks
        return {}

def calculate_score(row):
    score = 0
    mcap = row['MarketCapCr']
    if 500 < mcap < 20000: score += 6          # small-mid cap bias
    if row['ROE'] > 18: score += 5
    if row['Debt/Equity'] < 0.4 and row['Debt/Equity'] >= 0: score += 5
    if 0 < row['PE'] < 25: score += 4
    if row['RevenueGrowth'] > 12: score += 3
    if row['NetProfitMargin'] > 10: score += 2
    return score

if st.button("🚀 Start Hunt (uses \~200 API calls – be patient)"):
    if len(tickers) > 300:
        tickers = tickers[:300]  # safety cap for free tier
    
    with st.spinner(f"Scanning {len(tickers)} stocks... (5–12 min)"):
        progress_bar = st.progress(0)
        results = []
        
        for i, t in enumerate(tickers):
            fundamentals = fetch_fmp_fundamentals(t)
            if fundamentals:
                fundamentals['Score'] = calculate_score(fundamentals)
                results.append(fundamentals)
            time.sleep(0.4)  # avoid rate limit (FMP free \~4 req/sec ok, but safer)
            progress_bar.progress((i + 1) / len(tickers))
        
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values('Score', ascending=False).round(2)
            st.success(f"Hunt complete! {len(df)} stocks with usable data 🦍")
            st.dataframe(
                df.style.background_gradient(subset=['Score'], cmap='viridis')
                       .highlight_max(subset=['Score'], color='#90EE90'),
                height=650,
                use_container_width=True
            )
            
            # Quick top 10 highlight
            st.subheader("Top 10 Potential Beasts")
            st.dataframe(df.head(10)[['Ticker', 'Score', 'ROE', 'Debt/Equity', 'PE', 'RevenueGrowth']], use_container_width=True)
        else:
            st.error("No data returned. Check API key validity, rate limits, or try fewer stocks.")

st.markdown("---")
st.caption("Tips: Use Streamlit secrets for FMP_API_KEY in production. Run once/week. Add yfinance for 5Y CAGR later if needed. Built for the tribe – keep hunting!")
