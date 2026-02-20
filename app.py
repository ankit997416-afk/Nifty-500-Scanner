import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

st.set_page_config(page_title="Smart Stock Analyzer Pro", layout="wide", page_icon="📈")

st.markdown('<div style="font-size:40px;font-weight:800">📈 Smart Stock Analyzer Pro</div>', unsafe_allow_html=True)
st.caption("Quant Trend + Fundamentals + Risk + Market Regime + Sector Rotation")

# ───────────────── MARKET REGIME ─────────────────
@st.cache_data(ttl=900)
def market_regime():
    df = yf.Ticker("^NSEI").history(period="1y")
    sma50 = df['Close'].rolling(50).mean().iloc[-1]
    sma200 = df['Close'].rolling(200).mean().iloc[-1]
    return 1 if sma50 > sma200 else -1

# ───────────────── SECTOR MOMENTUM ─────────────────
SECTOR_ETF = {
    "IT":"^CNXIT",
    "BANK":"^NSEBANK",
    "FMCG":"^CNXFMCG",
    "AUTO":"^CNXAUTO",
    "PHARMA":"^CNXPHARMA",
    "METAL":"^CNXMETAL"
}

@st.cache_data(ttl=1800)
def sector_strength():
    strength={}
    for s,t in SECTOR_ETF.items():
        try:
            df=yf.Ticker(t).history(period="6mo")
            ret=df['Close'].pct_change(60).iloc[-1]
            strength[s]=ret
        except:
            strength[s]=0
    return strength

# ───────────────── DATA ─────────────────
@st.cache_resource
def session():
    return yf.Ticker

@st.cache_data(ttl=3600)
def load_price(symbol):
    try:
        df=session()(symbol).history(period="2y",auto_adjust=True)
        return df if len(df)>60 else None
    except:return None

@st.cache_data(ttl=3600)
def info(symbol):
    try:return session()(symbol).info
    except:return {}

@st.cache_data(ttl=3600)
def fin(symbol):
    try:
        t=session()(symbol)
        return t.balance_sheet,t.cashflow
    except:return None,None

# ───────────────── TECHNICAL ─────────────────
def technical(df):
    score=0;reasons=[]
    latest=df.iloc[-1]

    df['50']=df['Close'].rolling(50).mean()
    df['200']=df['Close'].rolling(200).mean()

    if latest['Close']>latest['50']:score+=1
    else:reasons.append("Below 50MA")

    if latest['50']>latest['200']:score+=1
    else:reasons.append("Weak trend")

    rsi=(100-(100/(1+(df['Close'].diff().clip(lower=0).rolling(14).mean()/
                     (-df['Close'].diff().clip(upper=0).rolling(14).mean()))))).iloc[-1]

    if rsi>52:score+=1
    else:reasons.append("Weak RSI")

    # overextension penalty
    dist=(latest['Close']-latest['200'])/latest['Close']
    if dist>0.35:
        score-=1
        reasons.append("Overextended")

    return max(score,0),reasons

# ───────────────── FUNDAMENTAL ─────────────────
def fundamental(i):
    score=0;reasons=[]
    if i.get("returnOnEquity",0)>0.18:score+=1
    else:reasons.append("Low ROE")
    if i.get("revenueGrowth",0)>0.1:score+=1
    else:reasons.append("Low growth")
    if 8<i.get("trailingPE",999)<35:score+=1
    else:reasons.append("PE extreme")
    return score,reasons

# ───────────────── RISK ─────────────────
def risk(i,bs,cf):
    score=0;reasons=[]
    if i.get("debtToEquity",999)<0.7:score+=1
    else:reasons.append("High debt")
    if i.get("beta",2)<1.4:score+=1
    else:reasons.append("Volatile")
    try:
        if cf is not None and cf.iloc[:,0].get("Total Cash From Operating Activities",0)>0:score+=1
        else:reasons.append("Weak cashflow")
    except:pass
    return score,reasons

# ───────────────── PROBABILITY MODEL ─────────────────
def probability(t,f,r):
    raw=t*0.45+f*0.35+r*0.20
    prob=1/(1+math.exp(-1.2*(raw-2.3)))

    if market_regime()==-1:
        prob*=0.75

    return int(prob*100)

# ───────────────── ANALYZE ─────────────────
def analyze(symbol):
    df=load_price(symbol)
    if df is None:return None
    i=info(symbol)
    bs,cf=fin(symbol)

    t,tr=technical(df)
    f,fr=fundamental(i)
    r,rr=risk(i,bs,cf)

    p=probability(t,f,r)
    return {"Symbol":symbol.replace(".NS",""),"Prob":p,"Reasons":", ".join(tr+fr+rr)}

# ───────────────── UI ─────────────────
st.subheader("Single Stock")
sym=st.text_input("Symbol",value="RELIANCE.NS")

if st.button("Analyze"):
    r=analyze(sym)
    if r:
        st.metric("Probability",f"{r['Prob']}%")
        if r["Prob"]>70:st.success("Favorable risk-reward")
        elif r["Prob"]>55:st.warning("Manage position size")
        else:st.error("Avoid currently")
        st.write(r["Reasons"])

# ───────────────── SCANNER ─────────────────
st.divider()
st.subheader("Quick Scanner")

stocks=["RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
        "LT.NS","SBIN.NS","ITC.NS","AXISBANK.NS","BAJFINANCE.NS",
        "MARUTI.NS","TITAN.NS","SUNPHARMA.NS","ONGC.NS"]

if st.button("Scan"):
    results=[]
    prog=st.progress(0)
    for i,s in enumerate(stocks):
        r=analyze(s)
        if r:results.append(r)
        prog.progress((i+1)/len(stocks))

    df=pd.DataFrame(results).sort_values("Prob",ascending=False)
    st.dataframe(df,use_container_width=True)

st.caption("Educational tool • Not financial advice")
