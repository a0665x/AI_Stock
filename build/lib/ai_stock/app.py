from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ai_stock.analytics import add_indicators, compute_correlation_table, compute_latest_technical_snapshot
from ai_stock.data_sources import DataRequest, load_history, normalize_ohlcv
from ai_stock.forecasting import build_decision_report


st.set_page_config(page_title="AI Stock Decision Board", layout="wide")
st.title("AI Stock Decision Board")
st.caption("ARM-friendly first version: yfinance/CSV data, technical factors, correlation table, ARIMA/linear forecast, Kelly sizing.")

with st.sidebar:
    source = st.radio("資料來源", ["yfinance", "csv"], horizontal=True)
    ticker_text = st.text_input("股票代號（逗號分隔）", "AAPL, MSFT, NVDA")
    period = st.selectbox("歷史區間", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    interval = st.selectbox("K線週期", ["1d", "1wk", "1mo"], index=0)
    horizon = st.slider("預測/決策 horizon（交易日）", 1, 30, 5)
    uploaded = st.file_uploader("或上傳 CSV（支援 date/ticker/open/high/low/close/volume 或中文欄位）", type=["csv"])
    run = st.button("更新分析", type="primary")

@st.cache_data(ttl=600)
def _load_yf(tickers: tuple[str, ...], period: str, interval: str) -> pd.DataFrame:
    return load_history(DataRequest(tickers, period=period, interval=interval, provider="yfinance"))

prices = pd.DataFrame()
if uploaded is not None:
    prices = normalize_ohlcv(pd.read_csv(uploaded))
elif run or ticker_text:
    tickers = tuple(t.strip() for t in ticker_text.split(",") if t.strip())
    prices = _load_yf(tickers, period, interval)

if prices.empty:
    st.warning("目前沒有價格資料。請輸入可由 yfinance 查詢的代號，或上傳 CSV。")
    st.stop()

st.subheader("歷史價格 / K線")
selected = st.selectbox("選擇圖表代號", sorted(prices["ticker"].unique()))
one = prices[prices["ticker"] == selected].sort_values("date")
fig = go.Figure(
    data=[
        go.Candlestick(
            x=one["date"], open=one["open"], high=one["high"], low=one["low"], close=one["close"], name=selected
        )
    ]
)
ind = add_indicators(one)
fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_20"], name="SMA20"))
fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_60"], name="SMA60"))
fig.update_layout(height=520, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

snapshot = compute_latest_technical_snapshot(prices)
correlations = compute_correlation_table(prices)
report = build_decision_report(prices, horizon=horizon)

c1, c2 = st.columns(2)
with c1:
    st.subheader("最新技術指標")
    st.dataframe(snapshot, use_container_width=True, hide_index=True)
with c2:
    st.subheader("股票市價/報酬相關性")
    st.dataframe(correlations, use_container_width=True, hide_index=True)

st.subheader("決策報表：買/賣/停損參考")
st.dataframe(report, use_container_width=True, hide_index=True)
st.download_button(
    "下載決策報表 CSV",
    report.to_csv(index=False).encode("utf-8-sig"),
    file_name="ai_stock_decision_report.csv",
    mime="text/csv",
)

st.info("提醒：這是研究與決策輔助，不是投資建議；Futu OpenAPI 實盤/即時串接需可執行 OpenD 的主機或遠端 OpenD。")
