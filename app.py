import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="🦍 Multibagger Hunter", layout="wide")
st.title("🦍 Multibagger Hunter – NSE Focus")
st.markdown("Hunt for potential 10x+ stocks: High ROE, low debt, growth at reasonable price. Data from Financial Modeling Prep (free tier).")

FMP_API_KEY = st.secrets.get("FMP_API_KEY", st.text_input("Enter your FMP API key (free from financialmodelingprep.com)", type="password"))

if not FMP_API_KEY:
    st.stop()

# NSE small/mid lists (you can update periodically)
SMALLCAP_URL = "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
MIDCAP_URL = "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv"

@st.cache_data(ttl=86400)  # 1 day
def get_nse_tickers():
    headers = {'User-Agent': 'Mozilla/5.0'}
    small = pd.read_csv(requests.get(SMALLCAP_URL, headers=headers).text)['Symbol'].tolist()
    mid = pd.read_csv(requests.get(MIDCAP_URL, headers=headers).text)['Symbol'].tolist()
    return [s + ".NS" for s in small + mid]

tickers = get_nse_tickers()

@st.cache_data(ttl=86400*7)  # cache fundamentals longer
def fetch_fmp_fundamentals(symbol):
    try:
        url = f"https://financialmodelingprep.com/api/v3/ratios/{symbol}?apikey={FMP_API_KEY}&limit=5"
        r = requests.get(url).json()
        if not r or isinstance(r, dict): return {}
        latest = r[0]  # most recent year/quarter
        return {
            'ROE': latest.get('returnOnEquityTTM', 0) * 100,
            'Debt/Equity': latest.get('debtEquityRatioTTM', 999),
            'PE': latest.get('priceEarningsRatio', 999),
            'RevenueGrowth': latest.get('revenueGrowthTTM', 0) * 100,
            'NetProfitMargin': latest.get('netProfitMarginTTM', 0) * 100,
            'MarketCapCr': latest.get('marketCap', 0) / 1e7 if latest.get('marketCap') else 0,
        }
    except:
        return {}

def calculate_multibagger_score(row):
    score = 0
    if 1000 < row['MarketCapCr'] < 20000: score += 5   # small-mid sweet spot
    if row['ROE'] > 18: score += 5
    if row['Debt/Equity'] < 0.4: score += 5
    if row['PE'] < 25 and row['PE'] > 0: score += 3
    if row['RevenueGrowth'] > 12: score += 3
    if row['NetProfitMargin'] > 10: score += 2
    return score

if st.button("🚀 Hunt (uses \~200–300 API calls – free tier ok for occasional run)"):
    with st.spinner("Fetching fundamentals... (this may take 5–10 min)"):
        data = []
        progress = st.progress(0)
        for i, t in enumerate(tickers[:300]):  # limit for sanity
            symbol = t.replace('.NS', '')
            fundamentals = fetch_fmp_fundamentals(symbol)
            time.sleep(0.3)  # polite rate limit
            if fundamentals:
                fundamentals['Ticker'] = symbol
                fundamentals['Score'] = calculate_multibagger_score(fundamentals)
                data.append(fundamentals)
            progress.progress((i+1)/300)

        if data:
            df = pd.DataFrame(data)
            df = df.sort_values('Score', ascending=False)
            st.success(f"Found {len(df)} stocks with data!")
            st.dataframe(
                df.style.background_gradient(subset=['Score'], cmap='viridis')
                  .format(precision=2),
                height=600,
                use_container_width=True
            )
        else:
            st.error("No data returned – check API key or rate limit.")

st.caption("Tips: Run once/week. Add your FMP key in Streamlit secrets for production. Next: add filters, CAGR from yfinance, export CSV.")
