from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from research_engine import CostAssumptions, add_sma_signals, backtest_long_only, load_price_csv

HERE = Path(__file__).resolve().parent
PRICE_DIR = HERE / "data" / "price"

DANH_SACH_MA = [
    "ACB", "BCM", "BID", "CTG", "DGC", "FPT", "GAS", "GVR", "HDB", "HPG",
    "LPB", "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
]

CHI_PHI = CostAssumptions(
    commission_bps_each_side=15.0,
    slippage_bps_each_side=5.0,
    sell_tax_bps=10.0,
)


def dinh_dang_so_vi(value: float, so_chu_so_thap_phan: int = 2) -> str:
    """Định dạng số theo thông lệ Việt Nam: 1.234.567,89."""
    if pd.isna(value):
        return "-"
    text = f"{float(value):,.{so_chu_so_thap_phan}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def dinh_dang_so_nguyen_vi(value: float | int) -> str:
    if pd.isna(value):
        return "-"
    return f"{int(round(float(value))):,}".replace(",", ".")


def dinh_dang_phan_tram_vi(value: float, so_chu_so_thap_phan: int = 2) -> str:
    return f"{dinh_dang_so_vi(value, so_chu_so_thap_phan)}%"


def doc_von_vnd(text: str) -> int | None:
    """Đọc giá trị vốn dạng 100.000.000 hoặc 100,000,000 thành số nguyên."""
    digits = re.sub(r"[^0-9]", "", str(text))
    if not digits:
        return None
    return int(digits)


def tao_bieu_do(df: pd.DataFrame, symbol: str):
    x = add_sma_signals(df, 10, 50)
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x["time"], y=x["close"], name="Giá đóng cửa",
            hovertemplate="%{x|%d/%m/%Y}<br>Giá: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x["time"], y=x["sma_short"], name="SMA10",
            hovertemplate="%{x|%d/%m/%Y}<br>SMA10: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x["time"], y=x["sma_long"], name="SMA50",
            hovertemplate="%{x|%d/%m/%Y}<br>SMA50: %{y:,.0f}<extra></extra>",
        )
    )

    mua = x[x["execute_signal"] == 1]
    ban = x[x["execute_signal"] == -1]

    fig.add_trace(
        go.Scatter(
            x=mua["time"], y=mua["open"], mode="markers", name="Điểm mua",
            marker=dict(symbol="triangle-up", size=9),
            hovertemplate="%{x|%d/%m/%Y}<br>Giá mua: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ban["time"], y=ban["open"], mode="markers", name="Điểm bán",
            marker=dict(symbol="triangle-down", size=9),
            hovertemplate="%{x|%d/%m/%Y}<br>Giá bán: %{y:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"SMA10/50 - {symbol}: tín hiệu và giao dịch mô phỏng",
        hovermode="x unified",
        xaxis_title="Ngày",
        yaxis_title="Giá (VNĐ)",
        legend_title="Chú giải",
        separators=",.",
    )
    fig.update_yaxes(tickformat=",.0f")
    return fig


def tao_bieu_do_nav(equity: pd.DataFrame):
    nav = equity[["time", "nav"]].copy()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=nav["time"],
            y=nav["nav"],
            mode="lines",
            name="Giá trị tài sản",
            hovertemplate="%{x|%d/%m/%Y}<br>NAV: %{y:,.0f} VNĐ<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="Ngày",
        yaxis_title="Giá trị tài sản (VNĐ)",
        hovermode="x unified",
        separators=",.",
        showlegend=False,
    )
    fig.update_yaxes(tickformat=",.0f")
    return fig


def dinh_dang_bang_giao_dich(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades

    cols = [
        "entry_time", "entry_price_raw", "exit_time", "exit_price_raw", "trade_return_pct"
    ]
    cols = [c for c in cols if c in trades.columns]

    out = trades[cols].copy()
    out = out.rename(columns={
        "entry_time": "Ngày mua",
        "entry_price_raw": "Giá mua (VNĐ)",
        "exit_time": "Ngày bán",
        "exit_price_raw": "Giá bán (VNĐ)",
        "trade_return_pct": "Tỷ suất giao dịch",
    })

    for c in ["Ngày mua", "Ngày bán"]:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c]).dt.strftime("%d/%m/%Y")

    for c in ["Giá mua (VNĐ)", "Giá bán (VNĐ)"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(dinh_dang_so_nguyen_vi)

    if "Tỷ suất giao dịch" in out.columns:
        out["Tỷ suất giao dịch"] = (
            pd.to_numeric(out["Tỷ suất giao dịch"], errors="coerce")
            .map(lambda x: dinh_dang_phan_tram_vi(x, 2))
        )

    return out


def main():
    st.set_page_config(page_title="SMA Cross VN30", layout="wide")

    st.title("SMA Cross VN30 - Phân tích chiến lược")
    st.caption(
        "Chiến lược sử dụng SMA10 và SMA50 trên dữ liệu ngày. Tín hiệu được xác nhận theo giá đóng cửa "
        "và giao dịch được mô phỏng tại giá mở cửa của phiên kế tiếp."
    )

    symbols = [s for s in DANH_SACH_MA if (PRICE_DIR / f"{s}.csv").exists()]
    if not symbols:
        st.error("Không tìm thấy dữ liệu giá trong thư mục data/price.")
        return

    st.sidebar.header("Thiết lập mô phỏng")
    symbol = st.sidebar.selectbox(
        "Mã cổ phiếu",
        symbols,
        index=symbols.index("MSN") if "MSN" in symbols else 0,
    )

    capital_text = st.sidebar.text_input("Vốn ban đầu (VNĐ)", value="100.000.000")
    capital = doc_von_vnd(capital_text)

    if capital is None or capital < 1_000_000:
        st.sidebar.error("Vốn ban đầu cần từ 1.000.000 VNĐ trở lên.")
        return

    with st.sidebar.expander("Thông số mô phỏng"):
        st.write("SMA ngắn: 10 phiên")
        st.write("SMA dài: 50 phiên")
        st.write("Phí giao dịch: 0,15% mỗi chiều")
        st.write("Trượt giá: 0,05% mỗi chiều")
        st.write("Thuế khi bán: 0,10%")

    df = load_price_csv(PRICE_DIR / f"{symbol}.csv")
    metrics, trades, equity = backtest_long_only(
        df,
        initial_capital=capital,
        costs=CHI_PHI,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng tỷ suất sinh lời", dinh_dang_phan_tram_vi(metrics["total_return_pct"], 2))
    c2.metric("Tăng trưởng bình quân năm", dinh_dang_phan_tram_vi(metrics["cagr_pct"], 2))
    c3.metric("Mức sụt giảm tối đa", dinh_dang_phan_tram_vi(metrics["max_drawdown_pct"], 2))
    c4.metric("Số giao dịch", dinh_dang_so_nguyen_vi(metrics["n_trades"]))

    st.plotly_chart(tao_bieu_do(df, symbol), use_container_width=True)

    st.subheader("Diễn biến giá trị tài sản")
    st.plotly_chart(tao_bieu_do_nav(equity), use_container_width=True)

    st.subheader("Danh sách giao dịch")
    bang = dinh_dang_bang_giao_dich(trades)

    if bang.empty:
        st.write("Giai đoạn dữ liệu không phát sinh chu kỳ mua - bán hoàn chỉnh theo quy tắc SMA10/50.")
    else:
        st.dataframe(bang, use_container_width=True, hide_index=True)

    st.caption(
        "Kết quả được tính trên dữ liệu lịch sử của 30 mã cổ phiếu trong dự án, sử dụng thống nhất "
        "quy tắc SMA10/50, thời điểm giao dịch và bộ chi phí mô phỏng."
    )


if __name__ == "__main__":
    main()
