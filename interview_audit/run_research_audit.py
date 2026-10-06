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

ROOT = Path(__file__).resolve().parents[1]
PRICE_DIR = ROOT / "data" / "price"
OUT_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FIXED_UNIVERSE = [
    "ACB", "BCM", "BID", "CTG", "DGC", "FPT", "GAS", "GVR", "HDB", "HPG",
    "LPB", "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
]

INITIAL_CAPITAL = 100_000_000
SHORT_WINDOW = 10
LONG_WINDOW = 50
RF_ANNUAL = 0.0

# Chỉ là kịch bản chi phí minh họa để stress-test, không phải biểu phí chính thức.
COSTS = CostAssumptions(
    commission_bps_each_side=15.0,
    slippage_bps_each_side=5.0,
    sell_tax_bps=10.0,
)


def _round(v, n=4):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    return round(float(v), n)


def main():
    rows = []
    all_trades = []

    for symbol in FIXED_UNIVERSE:
        path = PRICE_DIR / f"{symbol}.csv"
        if not path.exists():
            print(f"SKIP {symbol}: missing {path}")
            continue

        df = load_price_csv(path)
        metrics, trades, equity = backtest_long_only(
            df,
            initial_capital=INITIAL_CAPITAL,
            short_window=SHORT_WINDOW,
            long_window=LONG_WINDOW,
            costs=COSTS,
            rf_annual=RF_ANNUAL,
        )
        hold = buy_and_hold_metrics(df, INITIAL_CAPITAL, COSTS, RF_ANNUAL)

        row = {
            "symbol": symbol,
            "start_date": df["time"].min().date().isoformat(),
            "end_date": df["time"].max().date().isoformat(),
            "n_obs": int(len(df)),
            "n_trades": int(metrics["n_trades"]),
            "ending_nav": _round(metrics["ending_nav"], 2),
            "total_return_pct": _round(metrics["total_return_pct"], 2),
            "cagr_pct": _round(metrics["cagr_pct"], 2),
            "ann_vol_pct": _round(metrics["ann_vol_pct"], 2),
            "sharpe_rf0": _round(metrics["sharpe"], 3),
            "max_drawdown_pct": _round(metrics["max_drawdown_pct"], 2),
            "win_rate_pct": _round(metrics["win_rate_pct"], 2),
            "avg_trade_pct": _round(metrics["avg_trade_pct"], 2),
            "best_trade_pct": _round(metrics["best_trade_pct"], 2),
            "worst_trade_pct": _round(metrics["worst_trade_pct"], 2),
            "buy_hold_total_return_pct": _round(hold.get("total_return_pct"), 2),
            "buy_hold_cagr_pct": _round(hold.get("cagr_pct"), 2),
            "buy_hold_max_drawdown_pct": _round(hold.get("max_drawdown_pct"), 2),
        }
        rows.append(row)

        if len(trades):
            tmp = trades.copy()
            tmp.insert(0, "symbol", symbol)
            all_trades.append(tmp)

        if symbol == "MSN":
            trades.to_csv(OUT_DIR / "MSN_trades_revised.csv", index=False)
            equity.to_csv(OUT_DIR / "MSN_equity_revised.csv", index=False)

    summary = pd.DataFrame(rows).sort_values("total_return_pct", ascending=False)
    summary.to_csv(OUT_DIR / "backtest_summary_revised.csv", index=False)

    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(OUT_DIR / "all_trades_revised.csv", index=False)

    # Sensitivity chỉ nhằm kiểm tra vùng tham số, không chọn "tham số tối ưu".
    sensitivity_rows = []
    for fast in [5, 10, 15, 20]:
        for slow in [30, 50, 75, 100]:
            if fast >= slow:
                continue
            per_symbol = []
            for symbol in FIXED_UNIVERSE:
                path = PRICE_DIR / f"{symbol}.csv"
                if not path.exists():
                    continue
                df = load_price_csv(path)
                m, _, _ = backtest_long_only(
                    df,
                    initial_capital=INITIAL_CAPITAL,
                    short_window=fast,
                    long_window=slow,
                    costs=COSTS,
                    rf_annual=RF_ANNUAL,
                )
                per_symbol.append(m["total_return_pct"])
            if per_symbol:
                sensitivity_rows.append({
                    "fast_window": fast,
                    "slow_window": slow,
                    "n_symbols": len(per_symbol),
                    "median_total_return_pct": round(float(np.nanmedian(per_symbol)), 2),
                    "mean_total_return_pct": round(float(np.nanmean(per_symbol)), 2),
                    "positive_symbol_pct": round(float(np.mean(np.array(per_symbol) > 0) * 100), 2),
                })
    pd.DataFrame(sensitivity_rows).to_csv(OUT_DIR / "parameter_sensitivity_revised.csv", index=False)

    meta = {
        "research_scope": "Fixed universe of 30 tickers stored in the repository; not reconstructed historical VN30 constituents.",
        "signal": f"SMA{SHORT_WINDOW}/SMA{LONG_WINDOW} crossover on Close(t)",
        "execution": "Next trading day Open(t+1)",
        "adx": "Not implemented in the revised baseline",
        "initial_capital_vnd": INITIAL_CAPITAL,
        "cost_scenario": COSTS.as_dict(),
        "risk_free_rate_for_sharpe": RF_ANNUAL,
        "fractional_shares": True,
        "force_close_last_position": True,
        "corporate_actions": "Adjustment status of repository price series is not independently verified; remains a limitation.",
        "oos_note": "No clean untouched OOS is claimed because the original project/report already inspected the 2020-2025 history.",
        "generated_files": [
            "backtest_summary_revised.csv",
            "all_trades_revised.csv",
            "MSN_trades_revised.csv",
            "MSN_equity_revised.csv",
            "parameter_sensitivity_revised.csv",
        ],
    }
    (OUT_DIR / "audit_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(summary.to_string(index=False))
    print("\nSaved:", OUT_DIR)


if __name__ == "__main__":
    main()
