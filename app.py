import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")

st.title("📈 Smart Stock Analyzer")
st.caption("Trend + Fundamentals + Risk + Return Probability")

symbol = st.text_input("Enter NSE Symbol (Example: TCS.NS)", value="TCS.NS")


# ===================== PRICE LOADER (Yahoo + NSE Fallback) =====================
@st.cache_data(ttl=3600)
def load_price(symbol):

    # ---- TRY YAHOO ----
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2y", auto_adjust=True)
        if len(df) > 200:
            return df
    except:
        pass

    # ---- NSE FALLBACK ----
    try:
        base = symbol.replace(".NS","")
        url = f"https://www.nseindia.com/api/chart-databyindex?index={base}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/"
        }

        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        data = session.get(url, headers=headers, timeout=5).json()

        prices = pd.DataFrame(data['grapthData'], columns=['timestamp','Close'])
        prices['Date'] = pd.to_datetime(prices['timestamp'], unit='ms')
        prices.set_index('Date', inplace=True)
        prices.drop(columns=['timestamp'], inplace=True)

        return prices
    except:
        return None


# ===================== TECHNICAL ANALYSIS =====================
def technical_score(df):
    df['50MA'] = df['Close'].rolling(50).mean()
    df['150MA'] = df['Close'].rolling(150).mean()
    df['200MA'] = df['Close'].rolling(200).mean()

    latest = df.iloc[-1]
    score = 0

    if latest['Close'] > latest['50MA']: score += 1
    if latest['50MA'] > latest['150MA']: score += 1
    if latest['150MA'] > latest['200MA']: score += 1

    # Momentum
    momentum = (df['Close'].iloc[-1] / df['Close'].iloc[-120]) - 1
    if momentum > 0.15: score += 1

    return score, df


# ===================== FUNDAMENTALS =====================
@st.cache_data(ttl=3600)
def get_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except:
        return {}

def fundamental_score(info):
    score = 0

    if info.get("revenueGrowth",0) > 0.10: score += 1
    if info.get("earningsGrowth",0) > 0.10: score += 1
    if info.get("returnOnEquity",0) > 0.15: score += 1
    if info.get("operatingMargins",0) > 0.15: score += 1

    return score


# ===================== RISK CHECK (Banker Logic) =====================
@st.cache_data(ttl=3600)
def get_fin(symbol):
    try:
        t = yf.Ticker(symbol)
        return t.balance_sheet, t.cashflow
    except:
        return None, None

def risk_score(bs, cf):
    score = 0
    try:
        total_debt = bs.loc["Total Debt"][0]
        equity = bs.loc["Total Stockholder Equity"][0]
        fixed_assets = bs.loc["Property Plant Equipment"][0]

        # ALM safety
        if equity > fixed_assets:
            score += 1

        op_cash = cf.loc["Total Cash From Operating Activities"][0]
        if op_cash > 0:
            score += 1

    except:
        pass

    return score


# ===================== QUANT PROBABILITY MODEL =====================
def probability_model(t,f,r):
    raw = (t*0.4 + f*0.35 + r*0.25)
    prob = min(max(int(raw/4*100),5),95)
    return prob


# ===================== RUN =====================
if symbol:

    df = load_price(symbol)

    if df is None:
        st.error("Unable to fetch data currently. Try another stock.")
        st.stop()

    info = get_info(symbol)
    bs, cf = get_fin(symbol)

    t = technical_score(df)[0]
    f = fundamental_score(info)
    r = risk_score(bs, cf)

    prob = probability_model(t,f,r)

    # ---------- DISPLAY ----------
    col1,col2,col3,col4 = st.columns(4)

    col1.metric("📊 Technical", t)
    col2.metric("🏢 Fundamental", f)
    col3.metric("🛡 Risk Safety", r)
    col4.metric("🎯 Return Probability", f"{prob}%")

    if prob > 70:
        st.success("🟢 Strong Candidate")
    elif prob > 50:
        st.warning("🟡 Watchlist")
    else:
        st.error("🔴 Avoid")

    st.subheader("Trend Chart")
    st.line_chart(df[['Close','50MA','150MA','200MA']])
