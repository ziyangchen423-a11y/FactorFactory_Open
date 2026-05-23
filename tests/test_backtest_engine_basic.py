import sqlite3

import fundfactory_core.backtest.engine as engine
from fundfactory_core.backtest.engine import BacktestConfig, run_backtest
from fundfactory_core.data_pipeline.init_db import init_db


def _seed_backtest_db(db_path):
    init_db(db_path=str(db_path))
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for trade_date, pct in [("20240102", 1.0), ("20240103", 2.0), ("20240104", -1.0)]:
        cur.execute(
            "INSERT INTO trading_calendar (trade_date, is_open) VALUES (?, 1)",
            (trade_date,),
        )
        cur.execute(
            """
            INSERT INTO daily_data
            (ts_code, trade_date, open, high, low, close, pct_chg, vol, amount)
            VALUES (?, ?, 10, 11, 9, ?, ?, 1000, 10000)
            """,
            ("000001.SZ", trade_date, 10 + pct, pct),
        )
    cur.execute(
        "INSERT INTO stock_basic (ts_code, name, list_date) VALUES (?, ?, ?)",
        ("000001.SZ", "测试银行", "20230101"),
    )
    cur.execute(
        """
        INSERT INTO factor_values
        (factor_id, calc_date, ts_code, factor_value, rank_value, category)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("MOM_5D", "20240102", "000001.SZ", 1.0, 1.0, "momentum"),
    )
    conn.commit()
    conn.close()


def test_run_backtest_uses_trading_calendar_and_returns_result(tmp_path, monkeypatch):
    db_path = tmp_path / "backtest.db"
    output_dir = tmp_path / "output"
    _seed_backtest_db(db_path)
    monkeypatch.setattr(engine, "DB_PATH", str(db_path))

    result = run_backtest(
        BacktestConfig(
            start_date="20240101",
            end_date="20240104",
            factor_id="MOM_5D",
            rebalance_freq=20,
            top_pct=1.0,
        ),
        output_dir=str(output_dir),
    )

    assert result.run_id
    assert result.config.factor_id == "MOM_5D"
    assert result.equity_curve["trade_date"].tolist() == [
        "20240102",
        "20240103",
        "20240104",
    ]
    assert len(result.trades) > 0
    assert result.equity_curve["portfolio_value"].nunique() > 1
