from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple
import math

import numpy as np
import pandas as pd


TRADING_DAYS = 252


@dataclass(frozen=True)
class CostAssumptions:
    """
    Minh họa chi phí để stress-test tính khả thi của strategy.
    Đây là giả định mô hình, không phải biểu phí chính thức của bất kỳ CTCK nào.
    """
    commission_bps_each_side: float = 15.0
    slippage_bps_each_side: float = 5.0
    sell_tax_bps: float = 10.0

    @property
    def buy_rate(self) -> float:
        return (self.commission_bps_each_side + self.slippage_bps_each_side) / 10_000

    @property
    def sell_rate(self) -> float:
        return (self.commission_bps_each_side + self.slippage_bps_each_side + self.sell_tax_bps) / 10_000

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


def load_price_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path, parse_dates=["time"])
    required = {"time", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path}: thiếu cột {sorted(missing)}")

    out = df.sort_values("time").drop_duplicates("time").copy()
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["time", "open", "close"])
    if (out[["open", "close"]] <= 0).any().any():
        raise ValueError(f"{path}: tồn tại giá <= 0")
    return out.reset_index(drop=True)


def add_sma_signals(
    df: pd.DataFrame,
    short_window: int = 10,
    long_window: int = 50,
) -> pd.DataFrame:
    if short_window >= long_window:
        raise ValueError("short_window phải nhỏ hơn long_window")

    out = df.copy()
    out["sma_short"] = out["close"].rolling(short_window, min_periods=short_window).mean()
    out["sma_long"] = out["close"].rolling(long_window, min_periods=long_window).mean()

    prev_short = out["sma_short"].shift(1)
    prev_long = out["sma_long"].shift(1)

    cross_up = (out["sma_short"] > out["sma_long"]) & (prev_short <= prev_long)
    cross_down = (out["sma_short"] < out["sma_long"]) & (prev_short >= prev_long)

    out["signal_close"] = 0
    out.loc[cross_up, "signal_close"] = 1
    out.loc[cross_down, "signal_close"] = -1

    # Signal chỉ được biết sau Close(t); execution được dời sang phiên kế tiếp.
    out["execute_signal"] = out["signal_close"].shift(1).fillna(0).astype(int)
    return out


def _annualized_metrics(equity: pd.DataFrame, rf_annual: float = 0.0) -> Dict[str, float]:
    if equity.empty:
        return {
            "total_return_pct": np.nan,
            "cagr_pct": np.nan,
            "ann_vol_pct": np.nan,
            "sharpe": np.nan,
            "max_drawdown_pct": np.nan,
        }

    nav = equity["nav"].astype(float)
    start_nav = float(nav.iloc[0])
    end_nav = float(nav.iloc[-1])
    total_return = end_nav / start_nav - 1

    days = max((equity["time"].iloc[-1] - equity["time"].iloc[0]).days, 1)
    years = days / 365.25
    cagr = (end_nav / start_nav) ** (1 / years) - 1 if years > 0 and start_nav > 0 and end_nav > 0 else np.nan

    rets = nav.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ann_vol = rets.std(ddof=1) * math.sqrt(TRADING_DAYS) if len(rets) > 1 else np.nan
    rf_daily = (1 + rf_annual) ** (1 / TRADING_DAYS) - 1
    sharpe = ((rets.mean() - rf_daily) / rets.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(rets) > 1 and rets.std(ddof=1) > 0 else np.nan

    running_peak = nav.cummax()
    dd = nav / running_peak - 1
    max_dd = float(dd.min()) if len(dd) else np.nan

    return {
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100 if pd.notna(cagr) else np.nan,
        "ann_vol_pct": ann_vol * 100 if pd.notna(ann_vol) else np.nan,
        "sharpe": sharpe,
        "max_drawdown_pct": max_dd * 100 if pd.notna(max_dd) else np.nan,
    }


def backtest_long_only(
    df_price: pd.DataFrame,
    initial_capital: float = 100_000_000,
    short_window: int = 10,
    long_window: int = 50,
    costs: CostAssumptions | None = None,
    rf_annual: float = 0.0,
    force_close_last: bool = True,
) -> Tuple[Dict[str, float], pd.DataFrame, pd.DataFrame]:
    """
    Baseline:
    - SMA được tính trên Close(t).
    - Crossover biết sau khi phiên t kết thúc.
    - Lệnh được giả định thực thi tại Open(t+1), tránh same-close execution.
    - Long-only, toàn bộ vốn, cho phép fractional shares để tập trung vào research logic.
    - Chi phí được áp dụng theo bps giả định có thể cấu hình.
    """
    costs = costs or CostAssumptions()
    df = add_sma_signals(df_price, short_window, long_window)

    cash = float(initial_capital)
    shares = 0.0
    in_position = False
    entry = None
    trades: List[dict] = []
    equity_rows: List[dict] = []

    for i, row in df.iterrows():
        price_open = float(row["open"])
        price_close = float(row["close"])
        t = row["time"]
        exec_signal = int(row["execute_signal"])

        if exec_signal == 1 and not in_position:
            buy_price = price_open * (1 + costs.slippage_bps_each_side / 10_000)
            effective_buy = buy_price * (1 + costs.commission_bps_each_side / 10_000)
            shares = cash / effective_buy
            cash = 0.0
            in_position = True
            entry = {
                "entry_time": t,
                "entry_price_raw": price_open,
                "entry_price_effective": effective_buy,
                "entry_nav": shares * effective_buy,
            }

        elif exec_signal == -1 and in_position:
            sell_price = price_open * (1 - costs.slippage_bps_each_side / 10_000)
            net_sell = sell_price * (1 - (costs.commission_bps_each_side + costs.sell_tax_bps) / 10_000)
            cash = shares * net_sell
            trade_return = cash / entry["entry_nav"] - 1
            trades.append({
                **entry,
                "exit_time": t,
                "exit_price_raw": price_open,
                "exit_price_effective": net_sell,
                "trade_return_pct": trade_return * 100,
                "exit_nav": cash,
            })
            shares = 0.0
            in_position = False
            entry = None

        nav = cash if not in_position else shares * price_close
        equity_rows.append({
            "time": t,
            "nav": nav,
            "in_position": int(in_position),
            "close": price_close,
            "signal_close": int(row["signal_close"]),
            "execute_signal": exec_signal,
        })

    if in_position and force_close_last:
        row = df.iloc[-1]
        t = row["time"]
        price_close = float(row["close"])
        sell_price = price_close * (1 - costs.slippage_bps_each_side / 10_000)
        net_sell = sell_price * (1 - (costs.commission_bps_each_side + costs.sell_tax_bps) / 10_000)
        cash = shares * net_sell
        trade_return = cash / entry["entry_nav"] - 1
        trades.append({
            **entry,
            "exit_time": t,
            "exit_price_raw": price_close,
            "exit_price_effective": net_sell,
            "trade_return_pct": trade_return * 100,
            "exit_nav": cash,
            "forced_exit": True,
        })
        shares = 0.0
        in_position = False
        if equity_rows:
            equity_rows[-1]["nav"] = cash
            equity_rows[-1]["in_position"] = 0

    equity = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades)
    metrics = _annualized_metrics(equity, rf_annual=rf_annual)

    if len(trades_df):
        wins = trades_df["trade_return_pct"] > 0
        metrics.update({
            "n_trades": int(len(trades_df)),
            "win_rate_pct": float(wins.mean() * 100),
            "avg_trade_pct": float(trades_df["trade_return_pct"].mean()),
            "best_trade_pct": float(trades_df["trade_return_pct"].max()),
            "worst_trade_pct": float(trades_df["trade_return_pct"].min()),
            "ending_nav": float(equity["nav"].iloc[-1]),
        })
    else:
        metrics.update({
            "n_trades": 0,
            "win_rate_pct": np.nan,
            "avg_trade_pct": np.nan,
            "best_trade_pct": np.nan,
            "worst_trade_pct": np.nan,
            "ending_nav": float(equity["nav"].iloc[-1]) if len(equity) else initial_capital,
        })

    return metrics, trades_df, equity


def buy_and_hold_metrics(
    df_price: pd.DataFrame,
    initial_capital: float = 100_000_000,
    costs: CostAssumptions | None = None,
    rf_annual: float = 0.0,
) -> Dict[str, float]:
    costs = costs or CostAssumptions()
    df = df_price.sort_values("time").copy()
    if len(df) < 2:
        return {}

    buy_raw = float(df.iloc[0]["open"])
    buy_effective = buy_raw * (1 + costs.slippage_bps_each_side / 10_000) * (1 + costs.commission_bps_each_side / 10_000)
    shares = initial_capital / buy_effective

    # Chèn mốc vốn ban đầu ngay trước phiên đầu tiên để total return/CAGR
    # và drawdown đều đo từ đúng initial_capital, kể cả chi phí vào lệnh.
    first_time = pd.Timestamp(df.iloc[0]["time"])
    rows = [{"time": first_time - pd.Timedelta(seconds=1), "nav": float(initial_capital)}]
    for _, row in df.iterrows():
        rows.append({"time": row["time"], "nav": shares * float(row["close"])})

    sell_raw = float(df.iloc[-1]["close"])
    sell_effective = sell_raw * (1 - costs.slippage_bps_each_side / 10_000) * (1 - (costs.commission_bps_each_side + costs.sell_tax_bps) / 10_000)
    rows[-1]["nav"] = shares * sell_effective

    metrics = _annualized_metrics(pd.DataFrame(rows), rf_annual=rf_annual)
    metrics["ending_nav"] = rows[-1]["nav"]
    return metrics
