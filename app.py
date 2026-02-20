import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")

# ---------- STYLE ----------
st.markdown("""
<style>
.big-title {font-size:38px; font-weight:700;}
.card {padding:15px;border-radius:12px;background:#111827;}
.good {color:#22c55e;font-weight:600;}
.warn {color:#eab308;font-weight:600;}
.bad {color:#ef4444;font-weight:600;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">📈 Smart Stock Analyzer</div>', unsafe_allow_html=True)
st.caption("Trend + Fundamentals + Risk + Explainable Probability")

symbol = st.text_input("Analyze Stock", value="TCS.NS")


# ---------- DATA ----------
@st.cache_data(ttl=3600)
def load_price(symbol):
    try:
        df=yf.Ticker(symbol).history(period="2y",auto_adjust=True)
        if len(df)>10:return df
    except:pass
    return None

@st.cache_data(ttl=3600)
def get_info(symbol):
    try:return yf.Ticker(symbol).info
    except:return {}

@st.cache_data(ttl=3600)
def get_fin(symbol):
    try:
        t=yf.Ticker(symbol)
        return t.balance_sheet,t.cashflow
    except:return None,None


# ---------- SCORING ----------
def technical(df):
    n=len(df);score=0;reason=[]
    if n>=200:
        df['50']=df['Close'].rolling(50).mean()
        df['200']=df['Close'].rolling(200).mean()
        if df.iloc[-1]['Close']>df.iloc[-1]['50']:score+=1
        else:reason.append("Below 50MA")
        if df.iloc[-1]['50']>df.iloc[-1]['200']:score+=1
        else:reason.append("Weak long trend")
    elif n>=50:
        df['20']=df['Close'].rolling(20).mean()
        if df.iloc[-1]['Close']>df.iloc[-1]['20']:score+=1
        else:reason.append("No momentum")
    return score,reason

def fundamental(info):
    score=0;reason=[]
    if info.get("returnOnEquity",0)>0.15:score+=1
    else:reason.append("Low ROE")
    if info.get("revenueGrowth",0)>0.1:score+=1
    else:reason.append("Weak sales growth")
    return score,reason

def risk(bs,cf):
    score=0;reason=[]
    try:
        if bs.loc["Total Stockholder Equity"][0]>bs.loc["Property Plant Equipment"][0]:score+=1
        else:reason.append("Possible debt funding assets")
        if cf.loc["Total Cash From Operating Activities"][0]>0:score+=1
        else:reason.append("Negative operating cashflow")
    except:reason.append("Financial data incomplete")
    return score,reason

def probability(t,f,r):
    return min(max(int((t*0.45+f*0.35+r*0.20)/4*100),5),95)


# ---------- ANALYZE ----------
def analyze(symbol):
    df=load_price(symbol)
    if df is None:return None

    info=get_info(symbol)
    bs,cf=get_fin(symbol)

    t,tr=technical(df)
    f,fr=fundamental(info)
    r,rr=risk(bs,cf)

    p=probability(t,f,r)
    reasons=tr+fr+rr

    return df,t,f,r,p,reasons


# ---------- DISPLAY ----------
if symbol:
    res=analyze(symbol)
    if res:
        df,t,f,r,p,reasons=res

        c1,c2,c3,c4=st.columns(4)
        c1.metric("Technical",t)
        c2.metric("Fundamental",f)
        c3.metric("Risk",r)
        c4.metric("Probability",f"{p}%")

        st.progress(p/100)

        if p>70:st.markdown('<p class="good">Strong Candidate</p>',unsafe_allow_html=True)
        elif p>50:st.markdown('<p class="warn">Watchlist</p>',unsafe_allow_html=True)
        else:st.markdown('<p class="bad">Avoid</p>',unsafe_allow_html=True)

        if reasons:
            st.subheader("Why?")
            for r in reasons:st.write("•",r)

        st.subheader("Trend")
        st.line_chart(df["Close"])
