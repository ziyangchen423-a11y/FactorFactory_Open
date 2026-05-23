"""
Tests for fundfactory_core.data_pipeline.init_db.
"""
import sqlite3
import pytest
from fundfactory_core.data_pipeline.init_db import init_db


# All tables defined in open_core.sql
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


def test_init_db_creates_database_file(tmp_path):
    """init_db must create the database file at the given path."""
    db_path = str(tmp_path / "test_open.db")
    init_db(db_path=db_path)
    import os

    assert os.path.exists(db_path), "database file was not created"


def test_init_db_creates_all_nine_tables(tmp_path):
    """init_db must create all nine Open core tables."""
    db_path = str(tmp_path / "test_open9.db")
    init_db(db_path=db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    for table in OPEN_CORE_TABLES:
        assert table in tables, f"table '{table}' not found in database"


def test_init_db_idempotent(tmp_path):
    """Running init_db twice must not raise an error."""
    db_path = str(tmp_path / "test_open_idem.db")
    init_db(db_path=db_path)
    init_db(db_path=db_path)  # must not raise

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    )
    count = cursor.fetchone()[0]
    conn.close()
    assert count >= len(OPEN_CORE_TABLES)
