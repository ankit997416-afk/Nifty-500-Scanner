import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")

# ---------------- STYLE ----------------
st.markdown("""
<style>
.big-title {font-size:36px;font-weight:700;}
.good {color:#22c55e;font-weight:600;}
.warn {color:#eab308;font-weight:600;}
.bad {color:#ef4444;font-weight:600;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">📈 Smart Stock Analyzer</div>', unsafe_allow_html=True)
st.caption("Trend + Fundamentals + Risk + Market Scanner")

# ================= DATA FUNCTIONS =================

@st.cache_data(ttl=3600)
def load_price(symbol):
    try:
        df = yf.Ticker(symbol).history(period="2y", auto_adjust=True)
        if len(df) > 20:
            return df
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def get_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except:
        return {}

@st.cache_data(ttl=3600)
def get_fin(symbol):
    try:
        t = yf.Ticker(symbol)
        return t.balance_sheet, t.cashflow
    except:
        return None, None

@st.cache_data(ttl=86400)
def get_nse_index(index):

    url = f"https://www.nseindia.com/api/equity-stockIndices?index={index}"

    headers = {
        "User-Agent":"Mozilla/5.0",
        "Accept-Language":"en-US,en;q=0.9",
        "Referer":"https://www.nseindia.com/"
    }

    s = requests.Session()
    s.get("https://www.nseindia.com", headers=headers, timeout=5)
    data = s.get(url, headers=headers, timeout=5).json()

    stocks = [item['symbol'] + ".NS" for item in data['data']]
    return stocks

# ================= SCORING =================

def technical(df):
    n = len(df)
    score = 0
    reasons = []

    if n >= 200:
        df['50'] = df['Close'].rolling(50).mean()
        df['200'] = df['Close'].rolling(200).mean()

        if df.iloc[-1]['Close'] > df.iloc[-1]['50']:
            score += 1
        else:
            reasons.append("Below 50MA")

        if df.iloc[-1]['50'] > df.iloc[-1]['200']:
            score += 1
        else:
            reasons.append("Weak long trend")

    elif n >= 50:
        df['20'] = df['Close'].rolling(20).mean()
        if df.iloc[-1]['Close'] > df.iloc[-1]['20']:
            score += 1
        else:
            reasons.append("No short momentum")

    else:
        reasons.append("Limited price history")

    return score, reasons


def fundamental(info):
    score = 0
    reasons = []

    if info.get("returnOnEquity",0) > 0.15:
        score += 1
    else:
        reasons.append("Low ROE")

    if info.get("revenueGrowth",0) > 0.1:
        score += 1
    else:
        reasons.append("Weak sales growth")

    return score, reasons


def risk(bs,cf):
    score = 0
    reasons = []

    try:
        if bs.loc["Total Stockholder Equity"][0] > bs.loc["Property Plant Equipment"][0]:
            score += 1
        else:
            reasons.append("Assets funded by debt")

        if cf.loc["Total Cash From Operating Activities"][0] > 0:
            score += 1
        else:
            reasons.append("Negative operating cashflow")
    except:
        reasons.append("Incomplete financial data")

    return score, reasons


def probability(t,f,r):
    raw = t*0.45 + f*0.35 + r*0.20
    return min(max(int(raw/4*100),5),95)


def analyze(symbol):
    df = load_price(symbol)
    if df is None:
        return None

    info = get_info(symbol)
    bs,cf = get_fin(symbol)

    t,tr = technical(df)
    f,fr = fundamental(info)
    r,rr = risk(bs,cf)

    p = probability(t,f,r)
    reasons = tr + fr + rr

    return {
        "Symbol":symbol,
        "Tech":t,
        "Fund":f,
        "Risk":r,
        "Prob":p,
        "Reasons":", ".join(reasons),
        "df":df
    }

# ================= SINGLE STOCK =================

st.divider()
st.subheader("🔎 Analyze Single Stock")

symbol = st.text_input("Enter Symbol (Example: TCS.NS)", value="TCS.NS")

if symbol:
    result = analyze(symbol)
    if result:

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Technical",result["Tech"])
        c2.metric("Fundamental",result["Fund"])
        c3.metric("Risk",result["Risk"])
        c4.metric("Probability",f'{result["Prob"]}%')

        st.progress(result["Prob"]/100)

        if result["Prob"] > 70:
            st.markdown('<p class="good">Strong Candidate</p>', unsafe_allow_html=True)
        elif result["Prob"] > 50:
            st.markdown('<p class="warn">Watchlist</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="bad">Avoid</p>', unsafe_allow_html=True)

        if result["Reasons"]:
            st.write("**Why?**")
            st.write(result["Reasons"])

        st.line_chart(result["df"]["Close"])

# ================= CATEGORY SCANNER =================

st.divider()
st.subheader("📊 Scan Market Category")

category = st.selectbox(
    "Select Category",
    ["Large Cap","Mid Cap","Small Cap"]
)

scan_size = st.slider("How many stocks to scan",5,50,20)

if category=="Large Cap":
    STOCK_LIST = get_nse_index("NIFTY 100")
elif category=="Mid Cap":
    STOCK_LIST = get_nse_index("NIFTY MIDCAP 150")
else:
    STOCK_LIST = get_nse_index("NIFTY SMALLCAP 250")

if st.button("Run Scan"):

    selected = STOCK_LIST[:scan_size]
    results = []
    progress = st.progress(0)

    for i,s in enumerate(selected):
        r = analyze(s)
        if r:
            results.append(r)
        progress.progress((i+1)/len(selected))

    if results:
        table = pd.DataFrame(results).drop(columns=["df"])
        table = table.sort_values("Prob",ascending=False)
        st.dataframe(table,use_container_width=True)
