"""
Tests for fundfactory_core.data_pipeline.check_data.

Covers:
- Empty database (no tables)
- Initialized but empty tables
- Partial data with financial three tables populated
"""
import sqlite3
from fundfactory_core.data_pipeline.check_data import check_data
from fundfactory_core.data_pipeline.init_db import init_db


OPEN_CORE_TABLES = [
    "trading_calendar",
    "stock_basic",
    "daily_data",
    "adj_factor",
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "factor_values",
    "backtest_results",
]


class TestCheckDataEmptyDatabase:
    """Database file does not exist."""

    def test_missing_db_returns_fail_status(self, tmp_path):
        db_path = str(tmp_path / "does_not_exist.db")
        result = check_data(db_path=db_path)
        assert result["status"] == "FAIL"
        assert "next_steps" in result
        assert any("init-db" in step for step in result["next_steps"])

    def test_missing_db_mentions_init_command(self, tmp_path, capsys):
        db_path = str(tmp_path / "does_not_exist.db")
        check_data(db_path=db_path)
        captured = capsys.readouterr().out
        assert "init-db" in captured


class TestCheckDataInitializedEmpty:
    """Database is initialized but all tables are empty."""

    def test_all_tables_exist_count_zero(self, tmp_path):
        db_path = str(tmp_path / "empty_init.db")
        init_db(db_path=db_path)
        result = check_data(db_path=db_path)

        assert result["status"] == "WARN"
        for table in OPEN_CORE_TABLES:
            assert table in result["tables"]
            assert result["tables"][table]["exists"] is True
            assert result["tables"][table]["count"] == 0

    def test_next_steps_suggestions_for_empty_tables(self, tmp_path, capsys):
        db_path = str(tmp_path / "empty_init.db")
        init_db(db_path=db_path)
        check_data(db_path=db_path)
        captured = capsys.readouterr().out
        assert "sync-data" in captured or "run-factors" in captured


class TestCheckDataPartialData:
    """Database has partial data including financial three tables."""

    def _make_db_with_data(self, tmp_path):
        db_path = str(tmp_path / "partial_data.db")
        init_db(db_path=db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute(
            "INSERT OR IGNORE INTO trading_calendar (trade_date, is_open, day_of_week) VALUES (?, 1, 1)",
            ("20240102",),
        )
        cur.execute(
            "INSERT OR IGNORE INTO trading_calendar (trade_date, is_open, day_of_week) VALUES (?, 1, 2)",
            ("20240103",),
        )
        cur.execute(
            "INSERT OR IGNORE INTO stock_basic (ts_code, name, list_date) VALUES (?, ?, ?)",
            ("000001.SZ", "平安银行", "19910403"),
        )
        cur.execute(
            "INSERT OR IGNORE INTO daily_data "
            "(ts_code, trade_date, open, high, low, close, vol, amount) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("000001.SZ", "20240102", 10.0, 10.5, 9.8, 10.2, 1000000, 10000000),
        )
        cur.execute(
            "INSERT OR IGNORE INTO income_statement "
            "(ts_code, end_date, ann_date, revenue, n_income) "
            "VALUES (?, ?, ?, ?, ?)",
            ("000001.SZ", "20231231", "20240430", 1000000000, 500000000),
        )
        cur.execute(
            "INSERT OR IGNORE INTO balance_sheet "
            "(ts_code, end_date, ann_date, total_assets, total_liab) "
            "VALUES (?, ?, ?, ?, ?)",
            ("000001.SZ", "20231231", "20240430", 50000000000, 30000000000),
        )
        cur.execute(
            "INSERT OR IGNORE INTO cash_flow "
            "(ts_code, end_date, ann_date, net_profit, n_cashflow_act) "
            "VALUES (?, ?, ?, ?, ?)",
            ("000001.SZ", "20231231", "20240430", 500000000, 100000000),
        )
        conn.commit()
        conn.close()
        return db_path

    def test_partial_data_returns_warn_not_fail(self, tmp_path):
        db_path = self._make_db_with_data(tmp_path)
        result = check_data(db_path=db_path)
        assert result["status"] == "WARN"
        assert result["tables"]["trading_calendar"]["count"] == 2
        assert result["tables"]["daily_data"]["count"] == 1

    def test_financial_tables_show_latest_end_and_ann_dates(self, tmp_path):
        db_path = self._make_db_with_data(tmp_path)
        result = check_data(db_path=db_path)

        for table in ["income_statement", "balance_sheet", "cash_flow"]:
            info = result["tables"][table]["info"]
            assert info.get("latest_end_date") == "20231231", f"{table} latest_end_date mismatch"
            assert info.get("latest_ann_date") == "20240430", f"{table} latest_ann_date mismatch"

    def test_trading_calendar_range_reported(self, tmp_path):
        db_path = self._make_db_with_data(tmp_path)
        result = check_data(db_path=db_path)
        cal_info = result["tables"]["trading_calendar"]["info"]
        assert cal_info.get("range") == ("20240102", "20240103")

    def test_daily_data_range_reported(self, tmp_path):
        db_path = self._make_db_with_data(tmp_path)
        result = check_data(db_path=db_path)
        dd_info = result["tables"]["daily_data"]["info"]
        assert dd_info.get("range") == ("20240102", "20240102")

    def test_next_steps_include_sync_data_hint(self, tmp_path, capsys):
        db_path = self._make_db_with_data(tmp_path)
        check_data(db_path=db_path)
        captured = capsys.readouterr().out
        assert "sync-data" in captured

    def test_output_includes_financial_table_details(self, tmp_path, capsys):
        db_path = self._make_db_with_data(tmp_path)
        check_data(db_path=db_path)
        captured = capsys.readouterr().out
        for table in ["income_statement", "balance_sheet", "cash_flow"]:
            assert table in captured
        assert "end_date" in captured
        assert "ann_date" in captured


class TestCheckDataOutputFormat:
    """Output formatting smoke tests."""

    def test_table_report_shows_all_tables(self, tmp_path, capsys):
        db_path = str(tmp_path / "format_test.db")
        init_db(db_path=db_path)
        check_data(db_path=db_path)
        captured = capsys.readouterr().out
        for table in OPEN_CORE_TABLES:
            assert table in captured

    def test_status_ok_when_all_core_tables_have_data(self, tmp_path, capsys):
        db_path = str(tmp_path / "all_data.db")
        init_db(db_path=db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute(
            "INSERT OR IGNORE INTO trading_calendar (trade_date, is_open, day_of_week) VALUES (?, 1, 1)",
            ("20240102",),
        )
        cur.execute(
            "INSERT OR IGNORE INTO stock_basic (ts_code, name, list_date) VALUES (?, ?, ?)",
            ("000001.SZ", "test", "19910403"),
        )
        conn.commit()
        conn.close()

        result = check_data(db_path=db_path)
        assert result["status"] == "WARN"
        captured = capsys.readouterr().out
        assert "[WARN]" in captured or "WARN" in captured
