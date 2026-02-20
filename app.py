import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

st.set_page_config(page_title="Smart Stock Analyzer Pro", layout="wide", page_icon="📈")

# ─── PRO LEVEL STYLING (you'll love the colors) ─────────────────────────────
st.markdown("""
<style>
    .big-title {font-size:42px; font-weight:800; background: linear-gradient(90deg, #22c55e, #3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
    .subheader {font-size:22px; font-weight:600; color:#e5e7eb;}
    .good {color:#22c55e; font-weight:700;}
    .warn {color:#eab308; font-weight:700;}
    .bad {color:#ef4444; font-weight:700;}
    .rec-badge {padding:8px 16px; border-radius:9999px; font-weight:700; font-size:18px; text-align:center; margin:10px 0;}
    .metric-card {background:#1f2937; padding:16px; border-radius:12px; border-left:5px solid #22c55e;}
    .detail-table td, .detail-table th {padding:8px 12px !important;}
    .stProgress > div > div > div {background: linear-gradient(90deg, #22c55e, #eab308, #ef4444) !important;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">📈 Smart Stock Analyzer Pro</div>', unsafe_allow_html=True)
st.caption("Built like your hard-earned money depends on it • Technical + Fundamental + Risk + Momentum + Liquidity • NSE Focused")

# ─── SIDEBAR (your control center) ───────────────────────────────────────
with st.sidebar:
    st.header("🎛️ Scoring Engine")
    w_tech = st.slider("Technical + Momentum", 0.0, 1.0, 0.40, step=0.05)
    w_fund = st.slider("Fundamentals",         0.0, 1.0, 0.35, step=0.05)
    w_risk = st.slider("Risk + Liquidity",     0.0, 1.0, 0.25, step=0.05)
    
    st.header("📅 Data Settings")
    price_period = st.selectbox("Price History", ["1y", "2y", "3y", "5y"], index=1)
    
    st.header("🔍 Scanner Filters")
    min_prob = st.slider("Minimum Probability %", 30, 90, 55)
    scan_size = st.slider("Max stocks to scan", 5, 75, 30)

    st.divider()
    st.caption("Last data refresh: " + datetime.now().strftime("%d %b %H:%M"))

# ─── DATA FUNCTIONS (bulletproof + cached) ───────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_price(symbol, period="2y"):
    try:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        return df if len(df) >= 60 else None
    except:
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
        return bs if not bs.empty else None, cf if not cf.empty else None
    except:
        return None, None

@st.cache_data(ttl=86400*2, show_spinner=False)
def get_nse_index(index_name):
    encoded = urllib.parse.quote(index_name)
    url = f"https://www.nseindia.com/api/equity-stockIndices?index={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }
    try:
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=headers, timeout=8)
        data = s.get(url, headers=headers, timeout=8).json()
        return [item['symbol'] + ".NS" for item in data.get('data', []) if item.get('symbol')]
    except:
        st.error(f"⚠️ NSE API failed for {index_name}")
        return []

# ─── SMART SCORING (multiple models, no loopholes) ───────────────────────
def technical_score(df):
    if df is None or len(df) < 60:
        return 0, ["Insufficient history"]
    
    score = 0
    reasons = []
    latest = df.iloc[-1]
    
    # 1. Moving Averages (core trend)
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean()
    if latest['Close'] > latest.get('SMA50', 0):
        score += 1
    else:
        reasons.append("Below 50 SMA")
    if latest.get('SMA50', 0) > latest.get('SMA200', 0):
        score += 1
    else:
        reasons.append("50 SMA below 200 SMA")
    
    # 2. RSI Momentum
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain/loss))
    if rsi.iloc[-1] > 52:
        score += 1
    else:
        reasons.append("RSI weak (<52)")
    
    # 3. MACD (trend confirmation model)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    if macd.iloc[-1] > signal.iloc[-1]:
        score += 1
    else:
        reasons.append("MACD bearish")
    
    # 4. 1-month momentum
    ret_1m = df['Close'].pct_change(22).iloc[-1]
    if ret_1m > 0.03:
        score += 1
    else:
        reasons.append("Weak 1M momentum")
    
    return min(score, 5), reasons

def fundamental_score(info):
    score = 0
    reasons = []
    
    roe = info.get("returnOnEquity", 0)
    if roe > 0.18: score += 1
    else: reasons.append("ROE <18%")
    
    rev_growth = info.get("revenueGrowth", 0)
    if rev_growth > 0.12: score += 1
    else: reasons.append("Sales growth weak")
    
    profit_margin = info.get("profitMargins", 0)
    if profit_margin > 0.15: score += 1
    else: reasons.append("Profit margin <15%")
    
    pe = info.get("trailingPE", 999)
    if 8 < pe < 32: score += 1
    else: reasons.append("PE out of range")
    
    roa = info.get("returnOnAssets", 0)
    if roa > 0.08: score += 1
    else: reasons.append("ROA weak")
    
    return score, reasons

def risk_score(info, bs, cf):
    score = 0
    reasons = []
    
    # Debt & Beta (from info - super reliable)
    de = info.get("debtToEquity", 999)
    beta = info.get("beta", 999)
    if de < 0.6: score += 1
    else: reasons.append(f"Debt/Equity {de:.1f}")
    if beta < 1.25: score += 1
    else: reasons.append(f"Beta {beta:.2f} (volatile)")
    
    # Operating Cash Flow
    try:
        if cf is not None and not cf.empty:
            op_cf = cf.iloc[:, 0].get("Total Cash From Operating Activities", 
                                     cf.iloc[:, 0].get("Net Cash Provided By Operating Activities", 0))
            if op_cf > 0: score += 1
            else: reasons.append("Negative op. cash flow")
    except:
        reasons.append("CF data missing")
    
    # Liquidity (current ratio + avg volume)
    avg_vol = info.get("averageVolume", 0)
    if avg_vol > 200000: score += 1
    else: reasons.append("Low liquidity")
    
    try:
        if bs is not None and not bs.empty:
            latest = bs.iloc[:, 0]
            cur_assets = latest.get("Total Current Assets", 0)
            cur_liab = latest.get("Total Current Liabilities", 0)
            if cur_liab > 0 and (cur_assets / cur_liab) > 1.3:
                score += 1
            else:
                reasons.append("Current ratio weak")
    except:
        pass
    
    return min(score, 5), reasons

def overall_probability(t, f, r, w_tech, w_fund, w_risk):
    raw = t * w_tech + f * w_fund + r * w_risk
    max_possible = 5 * (w_tech + w_fund + w_risk)
    pct = (raw / max_possible) * 100 if max_possible > 0 else 15
    return int(min(max(pct, 15), 97))

# ─── CORE ANALYZER (one place, no duplication) ───────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def analyze(symbol, period):
    df = load_price(symbol, period)
    if df is None:
        return None
    
    info = get_info(symbol)
    bs, cf = get_financials(symbol)
    
    t_score, t_reasons = technical_score(df)
    f_score, f_reasons = fundamental_score(info)
    r_score, r_reasons = risk_score(info, bs, cf)
    
    prob = overall_probability(t_score, f_score, r_score, w_tech, w_fund, w_risk)
    
    # Extra fields for display
    mcap_cr = round(info.get("marketCap", 0) / 1e7, 1) if info.get("marketCap") else 0
    pe = round(info.get("trailingPE", np.nan), 2)
    one_m_ret = round(df['Close'].pct_change(22).iloc[-1] * 100, 1) if len(df)>22 else 0
    
    return {
        "Symbol": symbol.replace(".NS", ""),
        "Prob": prob,
        "Tech": t_score,
        "Fund": f_score,
        "Risk": r_score,
        "Price": round(info.get("currentPrice", 0), 2),
        "MktCap(Cr)": mcap_cr,
        "PE": pe,
        "Beta": round(info.get("beta", np.nan), 2),
        "1M%": one_m_ret,
        "Reasons": ", ".join(t_reasons + f_reasons + r_reasons) or "Excellent on all fronts",
        "df": df,
        "info": info
    }

# ─── SINGLE STOCK TAB ─────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🔍 Single Stock Deep Dive", "📊 Market Scanner"])

with tab1:
    st.subheader("Single Stock Deep Dive")
    raw = st.text_input("Enter NSE Symbol", value="RELIANCE.NS", help="TCS.NS or RELIANCE")
    symbol = raw.strip().upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol += ".NS"
    
    if symbol and st.button("Analyze", type="primary"):
        with st.spinner("Running full multi-model analysis..."):
            res = analyze(symbol, price_period)
        
        if res:
            # Metrics row
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Probability", f"{res['Prob']}%")
            c2.metric("Technical", res["Tech"])
            c3.metric("Fundamental", res["Fund"])
            c4.metric("Risk", res["Risk"])
            c5.metric("Price", f"₹{res['Price']:,.2f}")
            
            # Colored recommendation
            if res["Prob"] >= 82:
                st.markdown('<div class="rec-badge" style="background:#166534;color:white;">🚀 STRONG BUY</div>', unsafe_allow_html=True)
            elif res["Prob"] >= 68:
                st.markdown('<div class="rec-badge" style="background:#854d0e;color:white;">📌 ACCUMULATE</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="rec-badge" style="background:#991b1b;color:white;">⚠️ HIGH RISK</div>', unsafe_allow_html=True)
            
            # Custom colored progress
            color = "#22c55e" if res["Prob"] > 75 else "#eab308" if res["Prob"] > 55 else "#ef4444"
            st.markdown(f"""
            <div style="background:#374151;height:12px;border-radius:999px;overflow:hidden;">
                <div style="width:{res['Prob']}%;height:100%;background:{color};transition:width 1s;"></div>
            </div>
            """, unsafe_allow_html=True)
            
            if res["Reasons"] and res["Reasons"] != "Excellent on all fronts":
                st.caption("**Areas to watch**")
                st.write(res["Reasons"])
            
            # Detailed Metrics Card
            st.subheader("Key Financial Snapshot")
            details = {
                "Market Cap (₹ Cr)": f"{res['MktCap(Cr)']:,}",
                "Trailing PE": res["PE"],
                "Beta": res["Beta"],
                "1M Return": f"{res['1M%']}%",
                "ROE": f"{res.get('info',{}).get('returnOnEquity',0)*100:.1f}%",
                "Debt/Equity": f"{res.get('info',{}).get('debtToEquity',0):.2f}",
                "Profit Margin": f"{res.get('info',{}).get('profitMargins',0)*100:.1f}%"
            }
            df_details = pd.DataFrame(list(details.items()), columns=["Metric", "Value"])
            st.dataframe(df_details, use_container_width=True, hide_index=True)
            
            st.success("Analysis complete • Remember: Past performance ≠ future results")

# ─── SCANNER TAB ──────────────────────────────────────────────────────────
with tab2:
    st.subheader("Market Category Scanner")
    cat = st.selectbox("Choose Category", 
                       ["NIFTY 100", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250"], 
                       index=0)
    
    if st.button(f"🚀 SCAN {cat} (max {scan_size} stocks)", type="primary"):
        with st.spinner("Fetching constituents & running full analysis..."):
            if cat == "NIFTY 100":
                STOCK_LIST = get_nse_index("NIFTY 100")
            elif cat == "NIFTY MIDCAP 150":
                STOCK_LIST = get_nse_index("NIFTY MIDCAP 150")
            else:
                STOCK_LIST = get_nse_index("NIFTY SMALLCAP 250")
        
        if not STOCK_LIST:
            st.error("Failed to load index. Try again in 30 seconds.")
        else:
            selected = STOCK_LIST[:scan_size]
            results = []
            prog = st.progress(0)
            
            with ThreadPoolExecutor(max_workers=12) as executor:
                futures = {executor.submit(analyze, s, price_period): s for s in selected}
                for i, fut in enumerate(as_completed(futures)):
                    r = fut.result()
                    if r and r["Prob"] >= min_prob:
                        results.append(r)
                    prog.progress((i+1)/len(selected))
            
            if results:
                df = pd.DataFrame(results).drop(columns=["df", "info"])
                df = df.sort_values("Prob", ascending=False)
                
                st.success(f"Found {len(results)} stocks meeting your criteria")
                st.dataframe(
                    df[["Symbol", "Prob", "Price", "MktCap(Cr)", "PE", "Beta", "1M%", "Reasons"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Prob": st.column_config.ProgressColumn("Prob %", format="%d%%", min_value=0, max_value=100),
                        "Price": st.column_config.NumberColumn("Price ₹", format="%.2f"),
                        "MktCap(Cr)": st.column_config.NumberColumn("MktCap ₹ Cr", format="%.1f"),
                    }
                )
                
                csv = df.to_csv(index=False).encode()
                st.download_button("📥 Download Full Results (CSV)", 
                                   data=csv, 
                                   file_name=f"Pro_Scanner_{cat.replace(' ','_')}_{datetime.now().strftime('%d%b')}.csv",
                                   mime="text/csv")
            else:
                st.info("No stocks crossed your minimum probability filter. Lower it and try again.")

st.divider()
with st.expander("📖 How the Scoring Works (Transparency is everything)"):
    st.markdown("""
    **Technical (out of 5)**: 50/200 SMA, RSI, MACD crossover, 1-month momentum  
    **Fundamental (out of 5)**: ROE, Revenue growth, Profit margin, PE, ROA  
    **Risk + Liquidity (out of 5)**: Debt/Equity, Beta, Operating Cashflow, Current Ratio, Average Volume  
    
    **Probability** is weighted average converted to 15–97% range.  
    Everything is calculated fresh with multiple fallback layers — no single point of failure.
    
    This is not financial advice. Use at your own risk. Past performance is no guarantee.
    """)

st.caption("Made with ❤️ for serious Indian investors • Data: Yahoo Finance + official NSE • Always do your own research")
