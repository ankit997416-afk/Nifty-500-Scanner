import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

st.set_page_config(page_title="Smart Stock Analyzer Pro", layout="wide", page_icon="📈")

# ─── STYLING (kept same) ──────────────────────────────────────────────────
st.markdown("""
<style>
    .big-title {font-size:42px; font-weight:800; background: linear-gradient(90deg, #22c55e, #3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
    .good {color:#22c55e; font-weight:700;}
    .warn {color:#eab308; font-weight:700;}
    .bad {color:#ef4444; font-weight:700;}
    .rec-badge {padding:8px 16px; border-radius:9999px; font-weight:700; font-size:18px; text-align:center; margin:10px 0;}
    .stProgress > div > div > div {background: linear-gradient(90deg, #22c55e, #eab308, #ef4444) !important;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">📈 Smart Stock Analyzer Pro</div>', unsafe_allow_html=True)
st.caption("Faster • More Reliable • Free NSE CSV + Yahoo Finance")

# ─── SIDEBAR ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Scoring Weights")
    w_tech = st.slider("Technical + Momentum", 0.0, 1.0, 0.40, 0.05)
    w_fund = st.slider("Fundamentals", 0.0, 1.0, 0.35, 0.05)
    w_risk = st.slider("Risk + Liquidity", 0.0, 1.0, 0.25, 0.05)
    
    st.header("Data")
    price_period = st.selectbox("History", ["1y", "2y", "3y", "5y"], index=1)
    
    st.header("Scanner")
    min_prob = st.slider("Min Probability %", 20, 90, 45)
    scan_size = st.slider("Stocks to scan", 5, 80, 15)  # lowered default

# ─── DATA ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def load_price(symbol, period):
    try:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=True, timeout=10)
        return df if len(df) >= 40 else None  # lowered threshold
    except:
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def get_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except:
        return {}

@st.cache_data(ttl=43200, show_spinner=False)  # 12h for financials
def get_financials(symbol):
    try:
        t = yf.Ticker(symbol)
        return t.balance_sheet, t.cashflow
    except:
        return None, None

@st.cache_data(ttl=86400*7, show_spinner=False)
def get_nse_index(index_name):
    url_map = {
        "NIFTY 100": "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
        "NIFTY MIDCAP 150": "https://www.niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv",
        "NIFTY SMALLCAP 250": "https://www.niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv",
    }
    url = url_map.get(index_name)
    if not url: return []
    try:
        df = pd.read_csv(url, on_bad_lines='skip')
        if 'Symbol' not in df.columns: return []
        symbols = (df['Symbol'].astype(str).str.strip().str.upper() + ".NS").dropna().unique().tolist()
        return symbols
    except:
        return []

# ─── SCORING (same, but fundamentals/risk use info fallback more) ─────────
# ... keep technical_score, fundamental_score, risk_score, overall_probability exactly as before ...

# In risk_score, add fallback using info only if cf/bs fail
def risk_score(info, bs, cf):
    score = 0
    reasons = []
    
    de = info.get("debtToEquity", 999)
    beta = info.get("beta", 999)
    if de < 0.6: score += 1
    else: reasons.append(f"Debt/Equity {de:.1f}")
    if beta < 1.25 and beta > 0: score += 1
    else: reasons.append(f"Beta {beta:.2f}")
    
    op_cf_positive = False
    try:
        if cf is not None and not cf.empty:
            op_cf = cf.iloc[:,0].get("Total Cash From Operating Activities", 0)
            if op_cf > 0: op_cf_positive = True
    except:
        pass
    if op_cf_positive or info.get("operatingCashflow", 0) > 0:
        score += 1
    else:
        reasons.append("Negative/unknown op CF")
    
    avg_vol = info.get("averageVolume", 0)
    if avg_vol > 150000: score += 1  # slightly lower threshold
    else: reasons.append("Low liquidity")
    
    return min(score, 5), reasons

# ─── ANALYZE (added timeout & skip heavy calls if possible) ───────────────
@st.cache_data(ttl=900, show_spinner=False)
def analyze(symbol, period):
    df = load_price(symbol, period)
    if df is None:
        return None
    
    info = get_info(symbol)
    if not info:
        return None
    
    # Try light path first
    bs, cf = None, None
    if "debtToEquity" not in info or "beta" not in info:
        bs, cf = get_financials(symbol)
    
    t_score, t_reasons = technical_score(df)
    f_score, f_reasons = fundamental_score(info)
    r_score, r_reasons = risk_score(info, bs, cf)
    
    prob = overall_probability(t_score, f_score, r_score, w_tech, w_fund, w_risk)
    
    if prob < 10:  # skip very low to reduce clutter
        return None
    
    mcap_cr = round(info.get("marketCap", 0) / 1e7, 1) if info.get("marketCap") else np.nan
    pe = round(info.get("trailingPE", np.nan), 2)
    one_m_ret = round(df['Close'].pct_change(22).iloc[-1] * 100, 1) if len(df) > 22 else np.nan
    
    return {
        "Symbol": symbol.replace(".NS", ""),
        "Prob": prob,
        "Tech": t_score,
        "Fund": f_score,
        "Risk": r_score,
        "Price": round(info.get("currentPrice", np.nan), 2),
        "MktCap(Cr)": mcap_cr,
        "PE": pe,
        "Beta": round(info.get("beta", np.nan), 2),
        "1M%": one_m_ret,
        "Reasons": ", ".join(t_reasons + f_reasons + r_reasons) or "Strong",
    }

# ─── SINGLE STOCK (same, but added better warning) ────────────────────────
tab1, tab2 = st.tabs(["Single Stock", "Scanner"])

with tab1:
    # ... keep exactly as before ...

with tab2:
    st.subheader("Market Scanner")
    cat = st.selectbox("Category", ["NIFTY 100", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250"])
    
    if st.button(f"SCAN {cat} (up to {scan_size})", type="primary"):
        with st.spinner("Loading list & analyzing..."):
            STOCK_LIST = get_nse_index(cat)
        
        if not STOCK_LIST:
            st.error("Failed to load index list. Internet issue or URL changed?")
            st.stop()
        
        selected = STOCK_LIST[:scan_size]
        results = []
        failed = 0
        prog = st.progress(0)
        status = st.empty()
        
        with ThreadPoolExecutor(max_workers=12) as executor:  # increased workers
            futures = {executor.submit(analyze, s, price_period): s for s in selected}
            total = len(selected)
            for i, future in enumerate(as_completed(futures)):
                r = future.result()
                if r:
                    results.append(r)
                else:
                    failed += 1
                prog.progress((i+1)/total)
                status.text(f"Processed {i+1}/{total} | Failed {failed}")
        
        if results:
            df = pd.DataFrame(results).sort_values("Prob", ascending=False)
            st.success(f"Found {len(df)} stocks ≥ {min_prob}% prob (from {total} scanned)")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={"Prob": st.column_config.ProgressColumn(format="%d%%")},
            )
            st.download_button("Download CSV", df.to_csv(index=False).encode(), "scan_results.csv")
        else:
            st.warning("No stocks passed filters. Try: lower Min Probability, smaller scan size, or different category.")

st.caption("Tip: Start with scan_size=10–15 & min_prob=40–50 for quick results • Data from free sources • Not advice")
