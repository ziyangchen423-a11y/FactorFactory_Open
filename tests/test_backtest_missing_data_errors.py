import sqlite3

import pytest

import fundfactory_core.backtest.engine as engine
from fundfactory_core.backtest.engine import BacktestConfig, run_backtest
from fundfactory_core.data_pipeline.init_db import init_db


def _config():
    return BacktestConfig(
        start_date="20240102",
        end_date="20240104",
        factor_id="MOM_5D",
    )


def test_missing_trading_calendar_error_is_actionable(tmp_path, monkeypatch):
    db_path = tmp_path / "missing_calendar.db"
    init_db(db_path=str(db_path))
    monkeypatch.setattr(engine, "DB_PATH", str(db_path))

    with pytest.raises(ValueError, match="No trading dates found.*sync-data"):
        run_backtest(_config(), output_dir=str(tmp_path / "output"))


def test_missing_factor_values_error_is_actionable(tmp_path, monkeypatch):
    db_path = tmp_path / "missing_factor.db"
    init_db(db_path=str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO trading_calendar (trade_date, is_open) VALUES ('20240102', 1)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(engine, "DB_PATH", str(db_path))

    with pytest.raises(ValueError, match="No factor values found.*run-factors"):
        run_backtest(_config(), output_dir=str(tmp_path / "output"))


def test_missing_daily_data_error_is_actionable(tmp_path, monkeypatch):
    db_path = tmp_path / "missing_daily.db"
    init_db(db_path=str(db_path))
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO trading_calendar (trade_date, is_open) VALUES ('20240102', 1)")
    cur.execute(
        """
        INSERT INTO factor_values
        (factor_id, calc_date, ts_code, factor_value)
        VALUES ('MOM_5D', '20240102', '000001.SZ', 1.0)
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(engine, "DB_PATH", str(db_path))

    with pytest.raises(ValueError, match="No daily_data found.*sync-data"):
        run_backtest(_config(), output_dir=str(tmp_path / "output"))
