import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")
st.title("📈 Smart Stock Analyzer")
st.caption("Trend + Fundamentals + Risk + Probability")

# ---------- STOCK INPUT ----------
symbol = st.text_input("Enter NSE Symbol (Example: TCS.NS)", value="TCS.NS")

# ---------- LIQUID STOCK UNIVERSE ----------
SCAN_LIST = [
"RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
"ITC.NS","LT.NS","SBIN.NS","BHARTIARTL.NS","ASIANPAINT.NS",
"AXISBANK.NS","KOTAKBANK.NS","BAJFINANCE.NS","MARUTI.NS","TITAN.NS",
"ULTRACEMCO.NS","SUNPHARMA.NS","HCLTECH.NS","WIPRO.NS","ONGC.NS"
]

# ---------- PRICE LOADER ----------
@st.cache_data(ttl=3600)
def load_price(symbol):
    try:
        df = yf.Ticker(symbol).history(period="2y", auto_adjust=True)
        if len(df) > 10:
            return df
    except:
        pass
    return None

# ---------- TECHNICAL ----------
def technical_score(df):
    n = len(df)
    score = 0

    if n >= 200:
        df['50MA']=df['Close'].rolling(50).mean()
        df['150MA']=df['Close'].rolling(150).mean()
        df['200MA']=df['Close'].rolling(200).mean()
        latest=df.iloc[-1]
        if latest['Close']>latest['50MA']:score+=1
        if latest['50MA']>latest['150MA']:score+=1
        if latest['150MA']>latest['200MA']:score+=1
        if (df['Close'].iloc[-1]/df['Close'].iloc[-120]-1)>0.15:score+=1
        return score,"Long Trend"

    elif n>=50:
        df['20MA']=df['Close'].rolling(20).mean()
        df['50MA']=df['Close'].rolling(50).mean()
        latest=df.iloc[-1]
        if latest['Close']>latest['20MA']:score+=1
        if latest['20MA']>latest['50MA']:score+=1
        if (df['Close'].iloc[-1]/df['Close'].iloc[-40]-1)>0.08:score+=1
        return score,"Swing Trend"

    elif n>=20:
        if (df['Close'].iloc[-1]/df['Close'].iloc[-20]-1)>0.05:score+=1
        return score,"Short Momentum"

    return 0,"Too Little Data"

# ---------- FUNDAMENTAL ----------
@st.cache_data(ttl=3600)
def get_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except:
        return {}

def fundamental_score(info):
    score=0
    if info.get("revenueGrowth",0)>0.10:score+=1
    if info.get("earningsGrowth",0)>0.10:score+=1
    if info.get("returnOnEquity",0)>0.15:score+=1
    if info.get("operatingMargins",0)>0.15:score+=1
    return score

# ---------- RISK ----------
@st.cache_data(ttl=3600)
def get_fin(symbol):
    try:
        t=yf.Ticker(symbol)
        return t.balance_sheet,t.cashflow
    except:
        return None,None

def risk_score(bs,cf):
    score=0
    try:
        debt=bs.loc["Total Debt"][0]
        equity=bs.loc["Total Stockholder Equity"][0]
        fa=bs.loc["Property Plant Equipment"][0]
        if equity>fa:score+=1
        ocf=cf.loc["Total Cash From Operating Activities"][0]
        if ocf>0:score+=1
    except:
        pass
    return score

# ---------- PROBABILITY ----------
def probability(t,f,r):
    raw=t*0.45+f*0.35+r*0.20
    return min(max(int(raw/4*100),5),95)

# ---------- SINGLE STOCK ANALYSIS ----------
def analyze(symbol):
    df=load_price(symbol)
    if df is None: return None

    t,trend=technical_score(df)
    f=fundamental_score(get_info(symbol))
    bs,cf=get_fin(symbol)
    r=risk_score(bs,cf)
    p=probability(t,f,r)

    return {"Symbol":symbol,"Trend":trend,"Tech":t,"Fund":f,"Risk":r,"Prob":p,"df":df}

# ---------- RUN SINGLE ----------
if symbol:
    res=analyze(symbol)
    if res:
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Technical",res["Tech"])
        c2.metric("Fundamental",res["Fund"])
        c3.metric("Risk Safety",res["Risk"])
        c4.metric("Return Probability",f'{res["Prob"]}%')

        st.info(f'Model: {res["Trend"]}')

        if res["Prob"]>70:st.success("🟢 Strong Candidate")
        elif res["Prob"]>50:st.warning("🟡 Watchlist")
        else:st.error("🔴 Avoid")

        st.line_chart(res["df"]["Close"])

# ---------- AUTO SCANNER ----------
st.divider()
st.subheader("🔎 Auto Find Strong Stocks")

if st.button("Scan Market Leaders"):
    results=[]
    progress=st.progress(0)

    for i,s in enumerate(SCAN_LIST):
        r=analyze(s)
        if r: results.append(r)
        progress.progress((i+1)/len(SCAN_LIST))

    if results:
        table=pd.DataFrame(results).drop(columns=["df"])
        table=table.sort_values("Prob",ascending=False)
        st.dataframe(table,use_container_width=True)
