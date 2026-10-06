import pandas as pd

from research_engine import CostAssumptions, add_sma_signals, backtest_long_only


def _sample_df():
    # Dữ liệu giả lập đủ dài để tạo crossover rõ ràng.
    dates = pd.bdate_range("2024-01-01", periods=140)
    close = [100 + i * 0.2 for i in range(60)] + [112 - (i - 60) * 0.35 for i in range(60, 100)] + [98 + (i - 100) * 0.7 for i in range(100, 140)]
    return pd.DataFrame({
        "time": dates,
        "open": close,
        "high": [x * 1.01 for x in close],
        "low": [x * 0.99 for x in close],
        "close": close,
        "volume": [1_000_000] * len(dates),
    })


def test_signal_execution_is_lagged():
    df = add_sma_signals(_sample_df(), 10, 30)
    signal_days = df.index[df["signal_close"] != 0].tolist()
    assert signal_days, "Sample phải tạo ít nhất một crossover"
    for idx in signal_days:
        if idx + 1 < len(df):
            assert df.loc[idx + 1, "execute_signal"] == df.loc[idx, "signal_close"]


def test_max_drawdown_is_nav_based_and_metrics_exist():
    m, trades, eq = backtest_long_only(
        _sample_df(),
        short_window=10,
        long_window=30,
        costs=CostAssumptions(0, 0, 0),
    )
    assert "max_drawdown_pct" in m
    assert len(eq) > 0
    assert eq["nav"].min() > 0
    assert m["n_trades"] >= 1


def test_costs_do_not_improve_return():
    df = _sample_df()
    m0, _, _ = backtest_long_only(df, short_window=10, long_window=30, costs=CostAssumptions(0, 0, 0))
    mc, _, _ = backtest_long_only(df, short_window=10, long_window=30, costs=CostAssumptions(15, 5, 10))
    assert mc["ending_nav"] <= m0["ending_nav"] + 1e-6
