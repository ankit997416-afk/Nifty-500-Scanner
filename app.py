import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")
st.title("📈 Smart Stock Analyzer")
st.caption("Trend + Fundamentals + Risk + Probability")

symbol = st.text_input("Enter NSE Symbol (Example: TCS.NS)", value="TCS.NS")


# ---------------- PRICE LOADER ----------------
@st.cache_data(ttl=3600)
def load_price(symbol):

    # YAHOO
    try:
        df = yf.Ticker(symbol).history(period="2y", auto_adjust=True)
        if len(df) > 50:
            return df
    except:
        pass

    # NSE FALLBACK
    try:
        base = symbol.replace(".NS","")
        url = f"https://www.nseindia.com/api/chart-databyindex?index={base}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com/"
        }

        s = requests.Session()
        s.get("https://www.nseindia.com", headers=headers, timeout=5)
        data = s.get(url, headers=headers, timeout=5).json()

        prices = pd.DataFrame(data['grapthData'], columns=['timestamp','Close'])
        prices['Date'] = pd.to_datetime(prices['timestamp'], unit='ms')
        prices.set_index('Date', inplace=True)
        prices.drop(columns=['timestamp'], inplace=True)

        return prices
    except:
        return None


# ---------------- TECHNICAL ----------------
def technical_score(df):

    if len(df) < 200:
        return 0, df, False   # insufficient data

    df['50MA'] = df['Close'].rolling(50).mean()
    df['150MA'] = df['Close'].rolling(150).mean()
    df['200MA'] = df['Close'].rolling(200).mean()

    latest = df.iloc[-1]
    score = 0

    if latest['Close'] > latest['50MA']: score += 1
    if latest['50MA'] > latest['150MA']: score += 1
    if latest['150MA'] > latest['200MA']: score += 1

    momentum = (df['Close'].iloc[-1] / df['Close'].iloc[-120]) - 1
    if momentum > 0.15: score += 1

    return score, df, True


# ---------------- FUNDAMENTAL ----------------
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


# ---------------- RISK ----------------
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
        if equity > fixed_assets: score += 1

        op_cash = cf.loc["Total Cash From Operating Activities"][0]
        if op_cash > 0: score += 1
    except:
        pass
    return score


# ---------------- PROBABILITY ----------------
def probability(t,f,r):
    raw = t*0.45 + f*0.35 + r*0.20
    return min(max(int(raw/4*100),5),95)


# ---------------- RUN ----------------
if symbol:

    df = load_price(symbol)

    if df is None or len(df)==0:
        st.error("Unable to fetch price data currently.")
        st.stop()

    t,df,ok = technical_score(df)

    if not ok:
        st.warning("Not enough historical data for full technical analysis.")
        st.line_chart(df['Close'])
        st.stop()

    info = get_info(symbol)
    f = fundamental_score(info)

    bs,cf = get_fin(symbol)
    r = risk_score(bs,cf)

    prob = probability(t,f,r)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Technical",t)
    c2.metric("Fundamental",f)
    c3.metric("Risk Safety",r)
    c4.metric("Return Probability",f"{prob}%")

    if prob>70: st.success("🟢 Strong Candidate")
    elif prob>50: st.warning("🟡 Watchlist")
    else: st.error("🔴 Avoid")

    st.subheader("Trend")
    st.line_chart(df[['Close','50MA','150MA','200MA']])
