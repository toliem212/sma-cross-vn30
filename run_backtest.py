from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_engine import (
    CostAssumptions,
    backtest_long_only,
    buy_and_hold_metrics,
    load_price_csv,
)

HERE = Path(__file__).resolve().parent
PRICE_DIR = HERE / "data" / "price"
OUT_DIR = HERE / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DANH_SACH_MA = [
    "ACB", "BCM", "BID", "CTG", "DGC", "FPT", "GAS", "GVR", "HDB", "HPG",
    "LPB", "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
]

VON_BAN_DAU = 100_000_000
SMA_NGAN = 10
SMA_DAI = 50
LAI_SUAT_PHI_RUI_RO = 0.0

CHI_PHI = CostAssumptions(
    commission_bps_each_side=15.0,
    slippage_bps_each_side=5.0,
    sell_tax_bps=10.0,
)


def lam_tron(value, so_chu_so=4):
    if value is None or (
        isinstance(value, float)
        and np.isnan(value)
    ):
        return np.nan
    return round(float(value), so_chu_so)


def main():
    rows = []
    all_trades = []
    du_lieu = {}

    for symbol in DANH_SACH_MA:
        path = PRICE_DIR / f"{symbol}.csv"

        if path.exists():
            du_lieu[symbol] = load_price_csv(path)
        else:
            print(f"Bỏ qua {symbol}: thiếu tệp {path.name}")

    for symbol, df in du_lieu.items():
        metrics, trades, equity = backtest_long_only(
            df,
            initial_capital=VON_BAN_DAU,
            short_window=SMA_NGAN,
            long_window=SMA_DAI,
            costs=CHI_PHI,
            rf_annual=LAI_SUAT_PHI_RUI_RO,
        )

        hold = buy_and_hold_metrics(
            df,
            VON_BAN_DAU,
            CHI_PHI,
            LAI_SUAT_PHI_RUI_RO,
        )

        rows.append({
            "symbol": symbol,
            "start_date": df["time"].min().date().isoformat(),
            "end_date": df["time"].max().date().isoformat(),
            "n_obs": int(len(df)),
            "n_trades": int(metrics["n_trades"]),
            "ending_nav": lam_tron(metrics["ending_nav"], 2),
            "total_return_pct": lam_tron(
                metrics["total_return_pct"], 2
            ),
            "cagr_pct": lam_tron(metrics["cagr_pct"], 2),
            "ann_vol_pct": lam_tron(
                metrics["ann_vol_pct"], 2
            ),
            "sharpe_rf0": lam_tron(metrics["sharpe"], 3),
            "max_drawdown_pct": lam_tron(
                metrics["max_drawdown_pct"], 2
            ),
            "win_rate_pct": lam_tron(
                metrics["win_rate_pct"], 2
            ),
            "avg_trade_pct": lam_tron(
                metrics["avg_trade_pct"], 2
            ),
            "best_trade_pct": lam_tron(
                metrics["best_trade_pct"], 2
            ),
            "worst_trade_pct": lam_tron(
                metrics["worst_trade_pct"], 2
            ),
            "buy_hold_total_return_pct": lam_tron(
                hold.get("total_return_pct"), 2
            ),
            "buy_hold_cagr_pct": lam_tron(
                hold.get("cagr_pct"), 2
            ),
            "buy_hold_max_drawdown_pct": lam_tron(
                hold.get("max_drawdown_pct"), 2
            ),
        })

        if len(trades):
            tmp = trades.copy()
            tmp.insert(0, "symbol", symbol)
            all_trades.append(tmp)

        if symbol == "MSN":
            trades.to_csv(
                OUT_DIR / "MSN_trades.csv",
                index=False,
            )
            equity.to_csv(
                OUT_DIR / "MSN_equity.csv",
                index=False,
            )

    summary = (
        pd.DataFrame(rows)
        .sort_values(
            "total_return_pct",
            ascending=False,
        )
    )

    summary.to_csv(
        OUT_DIR / "backtest_summary.csv",
        index=False,
    )

    if all_trades:
        pd.concat(
            all_trades,
            ignore_index=True,
        ).to_csv(
            OUT_DIR / "all_trades.csv",
            index=False,
        )

    sensitivity_rows = []

    for fast in [5, 10, 15, 20]:
        for slow in [30, 50, 75, 100]:
            if fast >= slow:
                continue

            per_symbol = []

            for _, df in du_lieu.items():
                metrics, _, _ = backtest_long_only(
                    df,
                    initial_capital=VON_BAN_DAU,
                    short_window=fast,
                    long_window=slow,
                    costs=CHI_PHI,
                    rf_annual=LAI_SUAT_PHI_RUI_RO,
                )
                per_symbol.append(
                    metrics["total_return_pct"]
                )

            if per_symbol:
                sensitivity_rows.append({
                    "fast_window": fast,
                    "slow_window": slow,
                    "n_symbols": len(per_symbol),
                    "median_total_return_pct": round(
                        float(np.nanmedian(per_symbol)),
                        2,
                    ),
                    "mean_total_return_pct": round(
                        float(np.nanmean(per_symbol)),
                        2,
                    ),
                    "positive_symbol_pct": round(
                        float(
                            np.mean(
                                np.array(per_symbol) > 0
                            ) * 100
                        ),
                        2,
                    ),
                })

    pd.DataFrame(
        sensitivity_rows
    ).to_csv(
        OUT_DIR / "parameter_sensitivity.csv",
        index=False,
    )

    mo_ta = {
        "pham_vi_du_lieu": (
            "30 mã cổ phiếu trong bộ dữ liệu của dự án, "
            "sử dụng nhất quán cho toàn bộ phép thử."
        ),
        "tin_hieu": (
            f"Giao cắt SMA{SMA_NGAN}/SMA{SMA_DAI} "
            "tính theo giá đóng cửa ngày t."
        ),
        "thoi_diem_giao_dich": (
            "Giá mở cửa của phiên giao dịch kế tiếp t+1."
        ),
        "von_ban_dau_vnd": VON_BAN_DAU,
        "gia_dinh_chi_phi": CHI_PHI.as_dict(),
        "lai_suat_phi_rui_ro_dung_cho_sharpe":
            LAI_SUAT_PHI_RUI_RO,
        "tep_ket_qua": [
            "backtest_summary.csv",
            "all_trades.csv",
            "MSN_trades.csv",
            "MSN_equity.csv",
            "parameter_sensitivity.csv",
        ],
    }

    (OUT_DIR / "mo_ta_phuong_phap.json").write_text(
        json.dumps(
            mo_ta,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(summary.to_string(index=False))
    print(f"\nĐã lưu kết quả tại: {OUT_DIR}")


if __name__ == "__main__":
    main()
