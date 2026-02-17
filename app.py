import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(layout="wide")
st.title("Smart Stock Analyzer (Trend + Fundamentals + Risk)")

symbol = st.text_input("Enter NSE Symbol (Example: TCS.NS)")

# ---------------- SAFE DOWNLOAD ----------------
@st.cache_data(ttl=3600)   # 1 hour cache prevents rate limit
def load_price(symbol):
    for i in range(3):   # retry 3 times
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y", auto_adjust=True)
            if len(df) > 0:
                return df
        except:
            time.sleep(2)
    return None

@st.cache_data(ttl=3600)
def load_info(symbol):
    try:
        ticker = yf.Ticker(symbol)
        return ticker.info
    except:
        return {}

@st.cache_data(ttl=3600)
def load_financials(symbol):
    try:
        ticker = yf.Ticker(symbol)
        return ticker.balance_sheet, ticker.cashflow
    except:
        return None, None

# ---------------- TECHNICAL ----------------
def technical_analysis(df):
    df['50MA'] = df['Close'].rolling(50).mean()
    df['150MA'] = df['Close'].rolling(150).mean()
    df['200MA'] = df['Close'].rolling(200).mean()

    latest = df.iloc[-1]
    score = 0

    if latest['Close'] > latest['50MA']: score += 1
    if latest['50MA'] > latest['150MA']: score += 1
    if latest['150MA'] > latest['200MA']: score += 1

    return score, df

# ---------------- FUNDAMENTAL ----------------
def fundamental_check(info):
    score = 0

    if info.get("revenueGrowth",0) > 0.10: score += 1
    if info.get("earningsGrowth",0) > 0.10: score += 1
    if info.get("returnOnEquity",0) > 0.15: score += 1
    if info.get("operatingMargins",0) > 0.15: score += 1

    return score

# ---------------- RISK ----------------
def risk_check(bs, cf):
    score = 0
    try:
        total_debt = bs.loc["Total Debt"][0]
        equity = bs.loc["Total Stockholder Equity"][0]
        fixed_assets = bs.loc["Property Plant Equipment"][0]

        if equity > fixed_assets:
            score += 1

        op_cash = cf.loc["Total Cash From Operating Activities"][0]
        if op_cash > 0:
            score += 1

    except:
        pass

    return score

# ---------------- RUN ----------------
if symbol:

    df = load_price(symbol)

    if df is None or len(df) < 200:
        st.error("Data unavailable or Yahoo blocked request. Try again later.")
        st.stop()

    info = load_info(symbol)
    bs, cf = load_financials(symbol)

    t_score, df = technical_analysis(df)
    f_score = fundamental_check(info)
    r_score = risk_check(bs, cf)

    total = t_score + f_score + r_score

    st.subheader("Result")

    if total >= 6:
        st.success("🟢 Strong Candidate")
    elif total >= 4:
        st.warning("🟡 Watchlist")
    else:
        st.error("🔴 Avoid")

    st.write("Technical Score:", t_score)
    st.write("Fundamental Score:", f_score)
    st.write("Risk Score:", r_score)

    st.line_chart(df[['Close','50MA','150MA','200MA']])
