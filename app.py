import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

st.title("📊 NIFTY 500 Swing Scanner")
st.write("Low Frequency Weighted Model")

MIN_MARKET_CAP = 5000  # Crores
MIN_AVG_VOLUME = 500000
BUY_SCORE_THRESHOLD = 70

WEIGHTS = {
    "RSI": 20,
    "MACD": 20,
    "MA_STRUCTURE": 25,
    "ATR_BREAKOUT": 20,
    "VOLUME": 15
}

@st.cache_data
def get_nifty500():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    df = pd.read_csv(url)
    return [symbol + ".NS" for symbol in df['Symbol'].tolist()]

def analyze_stock(symbol):
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        if len(df) < 100:
            return None

        info = yf.Ticker(symbol).info
        market_cap = info.get("marketCap", 0)
        avg_volume = info.get("averageVolume", 0)

        market_cap_cr = market_cap / 1e7

        if market_cap_cr < MIN_MARKET_CAP or avg_volume < MIN_AVG_VOLUME:
            return None

        df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
        macd = ta.trend.MACD(df["Close"])
        df["MACD"] = macd.macd()
        df["MACD_signal"] = macd.macd_signal()
        df["ATR"] = ta.volatility.AverageTrueRange(
            df["High"], df["Low"], df["Close"], window=14
        ).average_true_range()

        df["MA50"] = df["Close"].rolling(50).mean()
        df["MA200"] = df["Close"].rolling(200).mean()
        df["VolumeAvg"] = df["Volume"].rolling(20).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        score = 0

        if 50 < latest["RSI"] < 65:
            score += WEIGHTS["RSI"]

        if latest["MACD"] > latest["MACD_signal"] and prev["MACD"] <= prev["MACD_signal"]:
            score += WEIGHTS["MACD"]

        if latest["Close"] > latest["MA50"] > latest["MA200"]:
            score += WEIGHTS["MA_STRUCTURE"]

        if latest["Close"] > df["Close"].rolling(20).max().iloc[-2] and \
           latest["ATR"] > df["ATR"].rolling(20).mean().iloc[-1]:
            score += WEIGHTS["ATR_BREAKOUT"]

        if latest["Volume"] > latest["VolumeAvg"]:
            score += WEIGHTS["VOLUME"]

        if score >= BUY_SCORE_THRESHOLD:
            return {
                "Symbol": symbol,
                "Score": score,
                "RSI": round(latest["RSI"], 2),
                "Price": round(latest["Close"], 2)
            }

    except:
        return None

    return None


if st.button("🔍 Scan NIFTY 500"):
    symbols = get_nifty500()
    results = []

    progress_bar = st.progress(0)

    for i, stock in enumerate(symbols):
        signal = analyze_stock(stock)
        if signal:
            results.append(signal)
        progress_bar.progress((i + 1) / len(symbols))

    if results:
        results_df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.success("Strong Buy Signals Found")
        st.dataframe(results_df)
    else:
        st.warning("No strong signals today.")
