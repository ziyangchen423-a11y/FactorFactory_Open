"""
Backtest engine - minimal daily-frequency stock backtester.

Supports:
- Single-factor backtesting
- Equal-weight portfolio
- Configurable rebalancing frequency
- Fee and slippage
- Benchmark comparison
- Key metrics: total return, annual return, max drawdown, Sharpe ratio, volatility

Does NOT support:
- Minute-level backtesting
- Tick撮合, complex order queues
- Margin/short selling
- Futures/options
- Multi-account
"""
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fundfactory_core.config.settings import (
    DB_PATH, DEFAULT_BENCHMARK, DEFAULT_FEE_RATE,
    DEFAULT_SLIPPAGE, DEFAULT_REBALANCE_FREQ, DEFAULT_TOP_PCT,
    DEFAULT_INITIAL_CASH, OUTPUT_DIR
)


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    start_date: str          # YYYYMMDD
    end_date: str            # YYYYMMDD
    factor_id: str           # Factor to use for ranking
    benchmark: str = DEFAULT_BENCHMARK
    rebalance_freq: int = DEFAULT_REBALANCE_FREQ  # trading days
    top_pct: float = DEFAULT_TOP_PCT              # top X% of stocks
    initial_cash: float = DEFAULT_INITIAL_CASH
    fee_rate: float = DEFAULT_FEE_RATE
    slippage_rate: float = DEFAULT_SLIPPAGE


@dataclass
class BacktestResult:
    """Backtest result container."""
    run_id: str
    config: BacktestConfig
    equity_curve: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    volatility: float


def _get_trade_dates(start: str, end: str) -> list:
    """Get all trading dates in range from the database."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    df = pd.read_sql("""
        SELECT trade_date FROM trading_calendar
        WHERE is_open = 1 AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, conn, params=[start, end])
    conn.close()
    return df["trade_date"].tolist()


def _get_factor_data(factor_id: str, trade_date: str) -> pd.DataFrame:
    """Get factor values for all stocks on a given date."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    df = pd.read_sql("""
        SELECT ts_code, factor_value
        FROM factor_values
        WHERE factor_id = ? AND calc_date = ?
        ORDER BY factor_value DESC
    """, conn, params=[factor_id, trade_date])
    conn.close()
    return df


def _get_daily_returns(trade_dates: list) -> pd.DataFrame:
    """Get daily returns for all stocks across trade dates."""
    if not trade_dates:
        return pd.DataFrame()
    dates_str = ",".join([f"'{d}'" for d in trade_dates])
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    df = pd.read_sql(f"""
        SELECT ts_code, trade_date, pct_chg
        FROM daily_data
        WHERE trade_date IN ({dates_str})
        ORDER BY ts_code, trade_date
    """, conn)
    conn.close()
    return df


def _count_factor_values(factor_id: str, trade_dates: list) -> int:
    """Count factor rows available on the configured trading dates."""
    if not trade_dates:
        return 0
    placeholders = ",".join(["?"] * len(trade_dates))
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM factor_values
        WHERE factor_id = ?
          AND calc_date IN ({placeholders})
    """, [factor_id] + trade_dates)
    count = cursor.fetchone()[0]
    conn.close()
    return int(count)


def _count_daily_rows(trade_dates: list) -> int:
    """Count daily price rows available on the configured trading dates."""
    if not trade_dates:
        return 0
    placeholders = ",".join(["?"] * len(trade_dates))
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM daily_data
        WHERE trade_date IN ({placeholders})
    """, trade_dates)
    count = cursor.fetchone()[0]
    conn.close()
    return int(count)


def _get_stock_pool(trade_date: str) -> set:
    """Get valid stock pool (exclude ST and stocks listed < 1 year)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cutoff_df = pd.read_sql("""
        SELECT trade_date FROM trading_calendar
        WHERE is_open = 1 AND trade_date < ?
        ORDER BY trade_date DESC
        LIMIT 252
    """, conn, params=[trade_date])
    conn.close()
    if len(cutoff_df) < 252:
        cutoff = trade_date
    else:
        cutoff = cutoff_df.iloc[-1]["trade_date"]

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    df = pd.read_sql("""
        SELECT ts_code FROM stock_basic
        WHERE name NOT LIKE '%ST%'
          AND list_date <= ?
          AND list_date != ''
    """, conn, params=[cutoff])
    conn.close()
    return set(df["ts_code"].tolist())


def _get_next_day_return(trade_date: str) -> pd.DataFrame:
    """Get next trading day's return for all stocks."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    next_date_df = pd.read_sql("""
        SELECT trade_date FROM trading_calendar
        WHERE is_open = 1 AND trade_date > ?
        ORDER BY trade_date LIMIT 1
    """, conn, params=[trade_date])
    conn.close()
    if next_date_df.empty:
        return pd.DataFrame(columns=["ts_code", "pct_chg"])
    next_date = next_date_df.iloc[0]["trade_date"]
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    df = pd.read_sql("""
        SELECT ts_code, pct_chg FROM daily_data
        WHERE trade_date = ?
    """, conn, params=[next_date])
    conn.close()
    return df


def run_backtest(config: BacktestConfig, output_dir: str = None) -> BacktestResult:
    """
    Run a backtest with the given configuration.

    Args:
        config: BacktestConfig with all parameters.
        output_dir: Directory to write result files.

    Returns:
        BacktestResult with equity curve, positions, trades, and metrics.
    """
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    run_id = str(uuid.uuid4())[:8]

    print(f"\nBacktest: {run_id}")
    print(f"  Factor: {config.factor_id}")
    print(f"  Period: {config.start_date} - {config.end_date}")
    print(f"  Rebalance every {config.rebalance_freq} days, top {config.top_pct*100:.0f}%")

    # Get all trading dates
    trade_dates = _get_trade_dates(config.start_date, config.end_date)
    if not trade_dates:
        raise ValueError(
            f"No trading dates found in range {config.start_date} - {config.end_date}. "
            "Run fundfactory sync-data --tables trading_calendar first."
        )

    if _count_factor_values(config.factor_id, trade_dates) == 0:
        raise ValueError(
            f"No factor values found for {config.factor_id} in range "
            f"{config.start_date} - {config.end_date}. "
            "Run fundfactory run-factors first."
        )

    if _count_daily_rows(trade_dates) == 0:
        raise ValueError(
            f"No daily_data found for return dates in range "
            f"{config.start_date} - {config.end_date}. "
            "Run fundfactory sync-data --tables daily_data first."
        )

    print(f"  Total trading days: {len(trade_dates)}")

    # Initialize portfolio
    cash = config.initial_cash
    positions = {}  # ts_code -> shares
    equity_curve = []
    all_trades = []

    # Get benchmark returns
    bm_returns = _get_daily_returns(trade_dates)
    if not bm_returns.empty:
        bm_returns = bm_returns[bm_returns["ts_code"] == config.benchmark]

    # Process each rebalance period
    n_periods = (len(trade_dates) + config.rebalance_freq - 1) // config.rebalance_freq
    rebalance_count = 0

    for period_idx in range(n_periods):
        period_start = period_idx * config.rebalance_freq
        period_end = min(period_start + config.rebalance_freq, len(trade_dates))
        period_dates = trade_dates[period_start:period_end]

        if not period_dates:
            continue

        # Get factor values on the first day of the period
        signal_date = period_dates[0]
        factor_df = _get_factor_data(config.factor_id, signal_date)
        if not factor_df.empty:
            rebalance_count += 1

        if factor_df.empty:
            # No factor data, skip this period
            period_returns = _get_daily_returns(period_dates)
            if not period_returns.empty:
                avg_return = period_returns.groupby("trade_date")["pct_chg"].mean()
                for td in period_dates:
                    if td in avg_return.index:
                        daily_pct = avg_return[td] / 100
                        cash *= (1 + daily_pct)
                        equity_curve.append({
                            "run_id": run_id,
                            "trade_date": td,
                            "portfolio_value": cash,
                            "cash": cash,
                        })
            continue

        # Get stock pool
        pool = _get_stock_pool(signal_date)

        # Filter factor data to stock pool
        factor_df = factor_df[factor_df["ts_code"].isin(pool)]

        # Select top N% by factor value
        n_stocks = max(1, int(len(factor_df) * config.top_pct))
        selected = factor_df.head(n_stocks)

        # Compute equal weight
        n_selected = len(selected)
        if n_selected == 0:
            continue
        weight = 1.0 / n_selected

        # Close old positions (with transaction costs)
        for ts_code, shares in list(positions.items()):
            if ts_code not in selected["ts_code"].values:
                # Get last close price
                conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                price_df = pd.read_sql("""
                    SELECT close FROM daily_data
                    WHERE ts_code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC LIMIT 1
                """, conn, params=[ts_code, signal_date])
                conn.close()
                if price_df.empty:
                    continue
                close_px = price_df.iloc[0]["close"]
                # Sell at close with slippage and fee
                sell_px = close_px * (1 - config.slippage_rate)
                proceeds = shares * sell_px
                fee = proceeds * config.fee_rate
                cash += proceeds - fee
                all_trades.append({
                    "run_id": run_id,
                    "trade_date": signal_date,
                    "ts_code": ts_code,
                    "action": "SELL",
                    "shares": shares,
                    "price": sell_px,
                    "amount": proceeds - fee,
                })
                del positions[ts_code]

        # Open new positions
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        prices_df = pd.read_sql(f"""
            SELECT ts_code, close FROM daily_data
            WHERE ts_code IN ({','.join(['?' for _ in selected['ts_code']]) })
              AND trade_date <= ?
            GROUP BY ts_code
        """, conn, params=selected["ts_code"].tolist() + [signal_date])
        conn.close()

        price_map = {row["ts_code"]: row["close"] for _, row in prices_df.iterrows()}

        for _, row in selected.iterrows():
            ts_code = row["ts_code"]
            if ts_code in positions:
                continue
            if ts_code not in price_map:
                continue
            close_px = price_map[ts_code]
            if close_px <= 0:
                continue
            buy_px = close_px * (1 + config.slippage_rate)
            shares_to_buy = int((cash * weight) / (buy_px * (1 + config.fee_rate)))
            if shares_to_buy <= 0:
                continue
            cost = shares_to_buy * buy_px
            fee = cost * config.fee_rate
            if cash >= cost + fee:
                cash -= cost + fee
                positions[ts_code] = shares_to_buy
                all_trades.append({
                    "run_id": run_id,
                    "trade_date": signal_date,
                    "ts_code": ts_code,
                    "action": "BUY",
                    "shares": shares_to_buy,
                    "price": buy_px,
                    "amount": cost + fee,
                })

        # Compute portfolio value for each day in the period
        for td in period_dates:
            td_returns = _get_next_day_return(td)
            td_returns = td_returns[td_returns["ts_code"].isin(positions.keys())]

            period_pnl = 0.0
            for _, ret_row in td_returns.iterrows():
                ts_code = ret_row["ts_code"]
                pct = ret_row["pct_chg"] / 100
                shares = positions.get(ts_code, 0)
                if shares > 0:
                    # Get close price
                    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                    px_df = pd.read_sql("""
                        SELECT close FROM daily_data
                        WHERE ts_code = ? AND trade_date <= ?
                        ORDER BY trade_date DESC LIMIT 1
                    """, conn, params=[ts_code, td])
                    conn.close()
                    if not px_df.empty:
                        close_px = px_df.iloc[0]["close"]
                        period_pnl += shares * close_px * pct

            # Also compute cash return
            cash_return = cash * (0.0 / 36500)  # negligible interest
            portfolio_value = cash
            if positions:
                conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                mark_df = pd.read_sql(f"""
                    SELECT d.ts_code, d.close
                    FROM daily_data d
                    JOIN (
                        SELECT ts_code, MAX(trade_date) AS trade_date
                        FROM daily_data
                        WHERE ts_code IN ({','.join(['?' for _ in positions])})
                          AND trade_date <= ?
                        GROUP BY ts_code
                    ) latest
                      ON d.ts_code = latest.ts_code
                     AND d.trade_date = latest.trade_date
                """, conn, params=list(positions.keys()) + [td])
                conn.close()
                mark_prices = {row["ts_code"]: row["close"] for _, row in mark_df.iterrows()}
                portfolio_value += sum(
                    shares * mark_prices.get(ts_code, price_map.get(ts_code, 0))
                    for ts_code, shares in positions.items()
                )

            equity_curve.append({
                "run_id": run_id,
                "trade_date": td,
                "portfolio_value": portfolio_value,
                "cash": cash,
            })

    # Build result DataFrames
    equity_df = pd.DataFrame(equity_curve)
    trades_df = pd.DataFrame(
        all_trades,
        columns=["run_id", "trade_date", "ts_code", "action", "shares", "price", "amount"],
    )
    positions_df = pd.DataFrame([
        {"run_id": run_id, "ts_code": tc, "shares": sh}
        for tc, sh in positions.items()
    ], columns=["run_id", "ts_code", "shares"])

    # Calculate metrics
    if equity_df.empty or len(equity_df) < 2:
        metrics = {
            "total_return": 0.0, "annual_return": 0.0,
            "max_drawdown": 0.0, "sharpe_ratio": 0.0, "volatility": 0.0
        }
    else:
        values = equity_df["portfolio_value"].values
        total_return = (values[-1] / values[0] - 1) * 100 if values[0] > 0 else 0.0

        # Annual return (annualized)
        n_days = len(equity_df)
        annual_return = ((values[-1] / values[0]) ** (252 / n_days) - 1) * 100 if values[0] > 0 and n_days > 0 else 0.0

        # Max drawdown
        peak = np.maximum.accumulate(values)
        drawdown = (values - peak) / peak * 100
        max_drawdown = float(np.min(drawdown))

        # Volatility (annualized)
        returns = np.diff(values) / values[:-1]
        volatility = float(np.std(returns) * np.sqrt(252) * 100) if len(returns) > 0 else 0.0

        # Sharpe ratio (assume 0% risk-free rate)
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0.0

        metrics = {
            "total_return": total_return,
            "annual_return": annual_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "volatility": volatility,
        }

    print(f"\n  Results:")
    print(f"    Total Return:   {metrics['total_return']:.2f}%")
    print(f"    Annual Return:  {metrics['annual_return']:.2f}%")
    print(f"    Max Drawdown:   {metrics['max_drawdown']:.2f}%")
    print(f"    Sharpe Ratio:   {metrics['sharpe_ratio']:.2f}")
    print(f"    Volatility:     {metrics['volatility']:.2f}%")

    # Write output files
    run_output_dir = Path(output_dir) / f"backtest_{run_id}"
    run_output_dir.mkdir(parents=True, exist_ok=True)

    equity_df.to_csv(run_output_dir / "equity_curve.csv", index=False)
    trades_df.to_csv(run_output_dir / "trades.csv", index=False)
    positions_df.to_csv(run_output_dir / "positions.csv", index=False)

    config_payload = {
        "start_date": config.start_date,
        "end_date": config.end_date,
        "factor_id": config.factor_id,
        "benchmark": config.benchmark,
        "rebalance_freq": config.rebalance_freq,
        "top_pct": config.top_pct,
        "initial_cash": config.initial_cash,
        "fee_rate": config.fee_rate,
        "slippage_rate": config.slippage_rate,
    }
    summary = {
        "run_id": run_id,
        "factor_id": config.factor_id,
        "start_date": config.start_date,
        "end_date": config.end_date,
        "benchmark": config.benchmark,
        "total_return": metrics["total_return"],
        "annual_return": metrics["annual_return"],
        "max_drawdown": metrics["max_drawdown"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "volatility": metrics["volatility"],
        "rebalance_count": rebalance_count,
        "trade_count": len(trades_df),
        "config": config_payload,
        "metrics": metrics,
        "output_dir": str(run_output_dir),
    }
    with open(run_output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(run_output_dir / "config.json", "w") as f:
        json.dump(config_payload, f, indent=2)

    print(f"\n  Results saved to: {run_output_dir}")

    return BacktestResult(
        run_id=run_id,
        config=config,
        equity_curve=equity_df,
        positions=positions_df,
        trades=trades_df,
        **metrics,
    )
