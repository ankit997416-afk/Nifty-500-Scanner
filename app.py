import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")

st.title("Smart Stock Analyzer (Trend + Fundamentals + Risk)")

symbol = st.text_input("Enter NSE Symbol (Example: TCS.NS)")

# ---------------- TECHNICAL ANALYSIS ----------------
def technical_analysis(df):
    df['50MA'] = df['Close'].rolling(50).mean()
    df['150MA'] = df['Close'].rolling(150).mean()
    df['200MA'] = df['Close'].rolling(200).mean()

    latest = df.iloc[-1]

    trend_score = 0
    if latest['Close'] > latest['50MA']: trend_score += 1
    if latest['50MA'] > latest['150MA']: trend_score += 1
    if latest['150MA'] > latest['200MA']: trend_score += 1

    return trend_score, df

# ---------------- FUNDAMENTAL CHECK ----------------
def fundamental_check(ticker):
    info = ticker.info
    score = 0

    try:
        if info.get("revenueGrowth",0) > 0.10: score += 1
        if info.get("earningsGrowth",0) > 0.10: score += 1
        if info.get("returnOnEquity",0) > 0.15: score += 1
        if info.get("operatingMargins",0) > 0.15: score += 1
    except:
        pass

    return score, info

# ---------------- RISK ANALYSIS ----------------
def risk_check(ticker):
    score = 0
    try:
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        total_debt = bs.loc["Total Debt"][0]
        equity = bs.loc["Total Stockholder Equity"][0]
        fixed_assets = bs.loc["Property Plant Equipment"][0]

        # ALM check
        if equity > fixed_assets:
            score += 1

        # Cash flow check
        op_cash = cf.loc["Total Cash From Operating Activities"][0]
        if op_cash > 0:
            score += 1

    except:
        pass

    return score

# ---------------- RUN ----------------
if symbol:
    ticker = yf.Ticker(symbol)

    df = ticker.history(period="2y")

    if len(df) > 200:

        t_score, df = technical_analysis(df)
        f_score, info = fundamental_check(ticker)
        r_score = risk_check(ticker)

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
