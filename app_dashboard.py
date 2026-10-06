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
    st.set_page_config(
        page_title="SMA Cross VN30",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1380px;
            padding-top: 1.6rem;
            padding-bottom: 2.2rem;
        }
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(49, 51, 63, 0.12);
        }
        [data-testid="stMetric"] {
            background: rgba(245, 247, 250, 0.78);
            border: 1px solid rgba(49, 51, 63, 0.10);
            padding: 0.9rem 1rem;
            border-radius: 0.8rem;
        }
        [data-testid="stMetricLabel"] {
            font-weight: 600;
        }
        .project-kicker {
            font-size: 0.88rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            color: #5f6b7a;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }
        .project-subtitle {
            color: #5f6b7a;
            font-size: 1rem;
            margin-top: -0.35rem;
            margin-bottom: 1rem;
        }
        .method-box {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 0.8rem;
            padding: 1rem 1.1rem;
            background: rgba(245, 247, 250, 0.55);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="project-kicker">Quantitative Research Project</div>', unsafe_allow_html=True)
    st.title("SMA Cross VN30")
    st.markdown(
        '<div class="project-subtitle">Phân tích chiến lược giao cắt SMA10/SMA50 trên dữ liệu ngày của 30 mã cổ phiếu</div>',
        unsafe_allow_html=True,
    )

    symbols = [s for s in DANH_SACH_MA if (PRICE_DIR / f"{s}.csv").exists()]
    if not symbols:
        st.error("Không tìm thấy dữ liệu giá trong thư mục data/price.")
        return

    st.sidebar.header("Thiết lập mô phỏng")
    st.sidebar.caption("Điều chỉnh mã cổ phiếu và vốn giả định để xem lại kết quả theo cùng một phương pháp.")
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

    with st.sidebar.expander("Thông số mô phỏng", expanded=False):
        st.write("SMA ngắn: **10 phiên**")
        st.write("SMA dài: **50 phiên**")
        st.write("Phí giao dịch: **0,15% mỗi chiều**")
        st.write("Trượt giá: **0,05% mỗi chiều**")
        st.write("Thuế khi bán: **0,10%**")

    st.sidebar.divider()
    st.sidebar.link_button(
        "Mã nguồn trên GitHub",
        "https://github.com/toliem212/sma-cross-vn30",
        width="stretch",
    )

    df = load_price_csv(PRICE_DIR / f"{symbol}.csv")
    metrics, trades, equity = backtest_long_only(
        df,
        initial_capital=capital,
        costs=CHI_PHI,
    )

    st.caption(
        f"Dữ liệu {symbol}: {df['time'].min():%d/%m/%Y} - {df['time'].max():%d/%m/%Y} · "
        f"Vốn giả định: {dinh_dang_so_nguyen_vi(capital)} VNĐ"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng tỷ suất sinh lời", dinh_dang_phan_tram_vi(metrics["total_return_pct"], 2))
    c2.metric("Tăng trưởng bình quân năm", dinh_dang_phan_tram_vi(metrics["cagr_pct"], 2))
    c3.metric("Mức sụt giảm tối đa", dinh_dang_phan_tram_vi(metrics["max_drawdown_pct"], 2))
    c4.metric("Số giao dịch", dinh_dang_so_nguyen_vi(metrics["n_trades"]))

    tab_tong_quan, tab_giao_dich, tab_phuong_phap = st.tabs(
        ["Tổng quan", "Giao dịch", "Phương pháp"]
    )

    with tab_tong_quan:
        st.subheader(f"Diễn biến giá và tín hiệu - {symbol}")
        st.plotly_chart(tao_bieu_do(df, symbol), width="stretch")

        st.subheader("Diễn biến giá trị tài sản")
        st.plotly_chart(tao_bieu_do_nav(equity), width="stretch")

    with tab_giao_dich:
        st.subheader(f"Danh sách giao dịch - {symbol}")
        bang = dinh_dang_bang_giao_dich(trades)

        if bang.empty:
            st.info("Giai đoạn dữ liệu không phát sinh chu kỳ mua - bán hoàn chỉnh theo quy tắc SMA10/50.")
        else:
            st.dataframe(bang, width="stretch", hide_index=True)

        if metrics["n_trades"] > 0:
            a1, a2, a3 = st.columns(3)
            a1.metric("Tỷ lệ giao dịch có lãi", dinh_dang_phan_tram_vi(metrics["win_rate_pct"], 2))
            a2.metric("Giao dịch tốt nhất", dinh_dang_phan_tram_vi(metrics["best_trade_pct"], 2))
            a3.metric("Giao dịch kém nhất", dinh_dang_phan_tram_vi(metrics["worst_trade_pct"], 2))

    with tab_phuong_phap:
        st.markdown(
            """
            <div class="method-box">
            <b>Quy tắc tín hiệu</b><br>
            Mua khi SMA10 cắt lên SMA50; bán khi SMA10 cắt xuống SMA50.<br><br>
            <b>Thời điểm giao dịch</b><br>
            Tín hiệu được xác nhận theo giá đóng cửa ngày t và giao dịch được mô phỏng tại giá mở cửa phiên t+1.<br><br>
            <b>Chi phí mô phỏng</b><br>
            Phí giao dịch 0,15% mỗi chiều; trượt giá 0,05% mỗi chiều; thuế khi bán 0,10%.<br><br>
            <b>Phạm vi dữ liệu</b><br>
            Cùng một quy tắc được áp dụng cho 30 mã cổ phiếu trong bộ dữ liệu của dự án.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.caption(
        "Dự án nghiên cứu định lượng bằng Python · "
        "Mã nguồn: github.com/toliem212/sma-cross-vn30"
    )


if __name__ == "__main__":
    main()
