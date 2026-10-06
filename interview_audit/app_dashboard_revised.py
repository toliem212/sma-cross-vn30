from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from research_engine import CostAssumptions, add_sma_signals, backtest_long_only, load_price_csv

HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "data" / "price").exists() else HERE.parent
PRICE_DIR = ROOT / "data" / "price"

COSTS = CostAssumptions(
    commission_bps_each_side=15.0,
    slippage_bps_each_side=5.0,
    sell_tax_bps=10.0,
)


def chart(df: pd.DataFrame, symbol: str):
    x = add_sma_signals(df, 10, 50)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x["time"], y=x["close"], name="Giá đóng cửa"))
    fig.add_trace(go.Scatter(x=x["time"], y=x["sma_short"], name="SMA10"))
    fig.add_trace(go.Scatter(x=x["time"], y=x["sma_long"], name="SMA50"))

    buy = x[x["execute_signal"] == 1]
    sell = x[x["execute_signal"] == -1]
    fig.add_trace(go.Scatter(x=buy["time"], y=buy["open"], mode="markers", name="Mua tại Open(t+1)",
                             marker=dict(symbol="triangle-up", size=9)))
    fig.add_trace(go.Scatter(x=sell["time"], y=sell["open"], mode="markers", name="Bán tại Open(t+1)",
                             marker=dict(symbol="triangle-down", size=9)))
    fig.update_layout(title=f"SMA10/50 - {symbol} - execution t+1", hovermode="x unified")
    return fig


def main():
    st.set_page_config(page_title="SMA Cross Research Audit", layout="wide")
    st.title("SMA Cross VN30 - Research Audit")
    st.caption("Baseline sửa lại cho phỏng vấn: SMA10/50, signal Close(t), execution Open(t+1), fixed universe, cost scenario minh họa.")

    files = sorted(PRICE_DIR.glob("*.csv"))
    symbols = [p.stem for p in files]
    if not symbols:
        st.error("Không tìm thấy data/price/*.csv")
        return

    symbol = st.sidebar.selectbox("Mã", symbols, index=symbols.index("MSN") if "MSN" in symbols else 0)
    capital = st.sidebar.number_input("Vốn giả định", min_value=1_000_000, value=100_000_000, step=1_000_000)

    df = load_price_csv(PRICE_DIR / f"{symbol}.csv")
    metrics, trades, equity = backtest_long_only(df, initial_capital=capital, costs=COSTS)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total return (net)", f"{metrics['total_return_pct']:.2f}%")
    c2.metric("CAGR", f"{metrics['cagr_pct']:.2f}%")
    c3.metric("Max Drawdown", f"{metrics['max_drawdown_pct']:.2f}%")
    c4.metric("Số giao dịch", f"{metrics['n_trades']}")

    st.plotly_chart(chart(df, symbol), use_container_width=True)
    st.subheader("Đường NAV")
    st.line_chart(equity.set_index("time")["nav"])
    st.subheader("Giao dịch")
    st.dataframe(trades, use_container_width=True)

    st.info("ADX không nằm trong baseline sửa lại. Universe là fixed list lưu trong repo, không được gọi là historical point-in-time VN30.")


if __name__ == "__main__":
    main()
