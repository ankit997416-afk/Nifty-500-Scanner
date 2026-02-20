import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Smart Stock Analyzer", layout="wide")
st.title("📈 Smart Stock Analyzer")
st.caption("Trend + Fundamentals + Risk + Probability")

# ================= SINGLE STOCK =================
symbol = st.text_input("Analyze Single Stock (Example: TCS.NS)", value="TCS.NS")


# ================= NSE INDEX FETCH =================
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


# ================= PRICE =================
@st.cache_data(ttl=3600)
def load_price(symbol):
    try:
        df = yf.Ticker(symbol).history(period="2y", auto_adjust=True)
        if len(df)>10:
            return df
    except:
        pass
    return None


# ================= TECHNICAL =================
def technical_score(df):

    n=len(df)
    score=0

    if n>=200:
        df['50']=df['Close'].rolling(50).mean()
        df['150']=df['Close'].rolling(150).mean()
        df['200']=df['Close'].rolling(200).mean()
        last=df.iloc[-1]
        if last['Close']>last['50']:score+=1
        if last['50']>last['150']:score+=1
        if last['150']>last['200']:score+=1
        if df['Close'].iloc[-1]/df['Close'].iloc[-120]-1>0.15:score+=1
        return score,"Long Trend"

    elif n>=50:
        df['20']=df['Close'].rolling(20).mean()
        df['50']=df['Close'].rolling(50).mean()
        last=df.iloc[-1]
        if last['Close']>last['20']:score+=1
        if last['20']>last['50']:score+=1
        if df['Close'].iloc[-1]/df['Close'].iloc[-40]-1>0.08:score+=1
        return score,"Swing Trend"

    elif n>=20:
        if df['Close'].iloc[-1]/df['Close'].iloc[-20]-1>0.05:score+=1
        return score,"Short Momentum"

    return 0,"Too Little Data"


# ================= FUNDAMENTAL =================
@st.cache_data(ttl=3600)
def get_info(symbol):
    try:
        return yf.Ticker(symbol).info
    except:
        return {}

def fundamental_score(info):
    s=0
    if info.get("revenueGrowth",0)>0.10:s+=1
    if info.get("earningsGrowth",0)>0.10:s+=1
    if info.get("returnOnEquity",0)>0.15:s+=1
    if info.get("operatingMargins",0)>0.15:s+=1
    return s


# ================= RISK =================
@st.cache_data(ttl=3600)
def get_fin(symbol):
    try:
        t=yf.Ticker(symbol)
        return t.balance_sheet,t.cashflow
    except:
        return None,None

def risk_score(bs,cf):
    s=0
    try:
        debt=bs.loc["Total Debt"][0]
        equity=bs.loc["Total Stockholder Equity"][0]
        fa=bs.loc["Property Plant Equipment"][0]
        if equity>fa:s+=1
        ocf=cf.loc["Total Cash From Operating Activities"][0]
        if ocf>0:s+=1
    except:
        pass
    return s


# ================= PROBABILITY =================
def probability(t,f,r):
    raw=t*0.45+f*0.35+r*0.20
    return min(max(int(raw/4*100),5),95)


# ================= ANALYZE FUNCTION =================
def analyze(symbol):
    df=load_price(symbol)
    if df is None: return None
    t,trend=technical_score(df)
    f=fundamental_score(get_info(symbol))
    bs,cf=get_fin(symbol)
    r=risk_score(bs,cf)
    p=probability(t,f,r)
    return {"Symbol":symbol,"Trend":trend,"Tech":t,"Fund":f,"Risk":r,"Prob":p,"df":df}


# ================= SINGLE STOCK OUTPUT =================
if symbol:
    res=analyze(symbol)
    if res:
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Technical",res["Tech"])
        c2.metric("Fundamental",res["Fund"])
        c3.metric("Risk Safety",res["Risk"])
        c4.metric("Return Probability",f'{res["Prob"]}%')
        st.info(f'Model Used: {res["Trend"]}')
        if res["Prob"]>70:st.success("🟢 Strong Candidate")
        elif res["Prob"]>50:st.warning("🟡 Watchlist")
        else:st.error("🔴 Avoid")
        st.line_chart(res["df"]["Close"])


# ================= MARKET SCANNER =================
st.divider()
st.subheader("🔎 Scan Market Category")

category = st.selectbox(
    "Select Category",
    ["Large Cap","Mid Cap","Small Cap"]
)

scan_size = st.slider("How many stocks to scan",5,60,20)

if category=="Large Cap":
    STOCK_LIST=get_nse_index("NIFTY 100")
elif category=="Mid Cap":
    STOCK_LIST=get_nse_index("NIFTY MIDCAP 150")
else:
    STOCK_LIST=get_nse_index("NIFTY SMALLCAP 250")

if st.button("Run Scan"):

    selected=STOCK_LIST[:scan_size]
    results=[]
    progress=st.progress(0)

    for i,s in enumerate(selected):
        r=analyze(s)
        if r:results.append(r)
        progress.progress((i+1)/len(selected))

    if results:
        table=pd.DataFrame(results).drop(columns=["df"])
        table=table.sort_values("Prob",ascending=False)
        st.dataframe(table,use_container_width=True)
