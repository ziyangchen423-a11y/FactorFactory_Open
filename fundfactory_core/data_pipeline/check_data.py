"""
Check data command - validates the Open core database.

Usage:
    python -m fundfactory_core.data_pipeline.check_data
    fundfactory check-data
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fundfactory_core.config.settings import DB_PATH


REQUIRED_TABLES = [
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

FINANCIAL_TABLES = {"income_statement", "balance_sheet", "cash_flow"}

NEXT_STEP_COMMANDS = {
    "trading_calendar": "fundfactory sync-data --tables trading_calendar",
    "stock_basic": "fundfactory sync-data --tables stock_basic",
    "daily_data": "fundfactory sync-data --tables daily_data --symbols <code> --start <YYYYMMDD>",
    "adj_factor": "fundfactory sync-data --tables adj_factor --symbols <code> --start <YYYYMMDD>",
    "income_statement": "fundfactory sync-data --tables income_statement --symbols <code>",
    "balance_sheet": "fundfactory sync-data --tables balance_sheet --symbols <code>",
    "cash_flow": "fundfactory sync-data --tables cash_flow --symbols <code>",
    "factor_values": "fundfactory run-factors --factor <FACTOR_ID> --date <YYYYMMDD>",
    "backtest_results": "fundfactory run-backtest --factor <FACTOR_ID>",
}


def check_data(db_path: str = None, *, verbose: bool = False) -> dict:
    """
    Check the Open core database for required tables and data.

    Returns a dict with status: "OK", "WARN", or "FAIL".

    Args:
        db_path: Path to SQLite database. Defaults to settings.DB_PATH.
        verbose: Print detailed results.

    Returns:
        dict with check results
    """
    db_path = db_path or DB_PATH
    results = {
        "status": "OK",
        "tables": {},
        "messages": [],
        "next_steps": [],
    }

    if not os.path.exists(db_path):
        results["status"] = "FAIL"
        results["messages"].append(f"Database not found: {db_path}")
        results["messages"].append("Run 'fundfactory init-db' first.")
        results["next_steps"].append("fundfactory init-db --db-path " + db_path)
        _print_summary(results)
        return results

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row["name"] for row in cursor.fetchall()}

    for table in REQUIRED_TABLES:
        if table in existing_tables:
            results["tables"][table] = {"exists": True, "count": None, "info": {}}
        else:
            results["tables"][table] = {"exists": False, "count": None, "info": {}}
            results["status"] = "FAIL"

    if results["status"] == "FAIL":
        missing = [t for t, v in results["tables"].items() if not v["exists"]]
        results["messages"].append(f"Missing tables: {', '.join(missing)}")
        results["messages"].append("Run 'fundfactory init-db' first.")
        for t in missing:
            results["next_steps"].append("fundfactory init-db")
            break
        conn.close()
        _print_summary(results)
        return results

    for table in REQUIRED_TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        results["tables"][table]["count"] = count

    for table in FINANCIAL_TABLES:
        cursor.execute(f"SELECT MAX(end_date), MAX(ann_date) FROM {table}")
        max_ed, max_ad = cursor.fetchone()
        results["tables"][table]["info"]["latest_end_date"] = max_ed
        results["tables"][table]["info"]["latest_ann_date"] = max_ad

    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM trading_calendar WHERE is_open = 1")
    cal_min, cal_max = cursor.fetchone()
    results["tables"]["trading_calendar"]["info"]["range"] = (cal_min, cal_max)

    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_data")
    dd_min, dd_max = cursor.fetchone()
    results["tables"]["daily_data"]["info"]["range"] = (dd_min, dd_max)

    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM adj_factor")
    af_min, af_max = cursor.fetchone()
    results["tables"]["adj_factor"]["info"]["range"] = (af_min, af_max)

    conn.close()

    for table in REQUIRED_TABLES:
        info = results["tables"][table]
        count = info["count"]
        if count == 0:
            results["status"] = "WARN"
            hint = NEXT_STEP_COMMANDS.get(table, f"fundfactory sync-data --tables {table}")
            results["next_steps"].append(f"{table} is empty. Hint: {hint}")

    _print_table_report(results, verbose=verbose)
    _print_summary(results)
    return results


def _print_table_report(results: dict, verbose: bool = False) -> None:
    print("\n" + "=" * 60)
    print("  FactorFactory Open - Data Quality Report")
    print("=" * 60)

    print(f"\n{'Table':<20} {'Exists':<8} {'Count':>10}")
    print("-" * 42)
    for table, info in results["tables"].items():
        exists_str = "YES" if info["exists"] else "NO"
        count_str = str(info["count"]) if info["count"] is not None else "-"
        print(f"  {table:<18} {exists_str:<8} {count_str:>10}")

    print("\n" + "-" * 60)
    print("  Detail")
    print("-" * 60)

    cal_info = results["tables"].get("trading_calendar", {}).get("info", {})
    if cal_info.get("range"):
        cal_min, cal_max = cal_info["range"]
        print(f"  trading_calendar    range: {cal_min} ~ {cal_max}")

    dd_info = results["tables"].get("daily_data", {}).get("info", {})
    if dd_info.get("range"):
        dd_min, dd_max = dd_info["range"]
        print(f"  daily_data          range: {dd_min} ~ {dd_max}")

    af_info = results["tables"].get("adj_factor", {}).get("info", {})
    if af_info.get("range"):
        af_min, af_max = af_info["range"]
        print(f"  adj_factor          range: {af_min} ~ {af_max}")

    for table in FINANCIAL_TABLES:
        info = results["tables"].get(table, {}).get("info", {})
        latest_ed = info.get("latest_end_date") or "N/A"
        latest_ad = info.get("latest_ann_date") or "N/A"
        print(f"  {table:<20} end_date: {latest_ed}  ann_date: {latest_ad}")

    if verbose:
        print("\n" + "-" * 60)
        print("  Verbose - Empty Table Check")
        print("-" * 60)
        for table, info in results["tables"].items():
            if info["count"] == 0:
                hint = NEXT_STEP_COMMANDS.get(table, f"fundfactory sync-data --tables {table}")
                print(f"  {table}: empty  -> {hint}")


def _print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    status = results["status"]
    if status == "OK":
        print("  [OK]   Database is ready.")
    elif status == "WARN":
        print("  [WARN] Database exists but some tables are empty.")
    else:
        print("  [FAIL] Database is not properly initialized.")

    if results.get("messages"):
        print("")
        for msg in results["messages"]:
            print(f"  {msg}")

    next_steps = results.get("next_steps", [])
    if next_steps:
        print("\n  Next Steps:")
        seen = set()
        for step in next_steps:
            if step not in seen:
                print(f"    {step}")
                seen.add(step)

    print()


def main():
    parser = argparse.ArgumentParser(description="Check FactorFactory Open database")
    parser.add_argument("--db-path", help="Path to SQLite database (default: from settings)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details")
    args = parser.parse_args()
    check_data(db_path=args.db_path, verbose=args.verbose)


if __name__ == "__main__":
    main()