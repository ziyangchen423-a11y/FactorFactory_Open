"""
Sync data command - fetches data from Tushare and writes to the Open database.

Usage:
    python -m fundfactory_core.data_pipeline.sync_data --provider tushare --start 20200101 --end 20260520
    factorfactory sync-data --provider tushare --start 20200101

Supported tables:
    trading_calendar  - exchange trading calendar
    stock_basic       - stock basic information
    daily_data        - daily K-line data (requires --symbols or syncs all stocks)
    adj_factor        - adjustment factors (requires --symbols or syncs all stocks)
    income_statement  - income statement (skeleton)
    balance_sheet     - balance sheet (skeleton)
    cash_flow         - cash flow statement (skeleton)
"""
import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fundfactory_core.config.settings import DB_PATH, DEFAULT_SYNC_START


# Table name aliases (CLI name -> actual table name(s))
TABLE_ALIASES = {
    "calendar": ["trading_calendar"],
    "trading_calendar": ["trading_calendar"],
    "stock_basic": ["stock_basic"],
    "daily": ["daily_data"],
    "daily_data": ["daily_data"],
    "adj_factor": ["adj_factor"],
    "financial": ["income_statement", "balance_sheet", "cash_flow"],
    "income_statement": ["income_statement"],
    "balance_sheet": ["balance_sheet"],
    "cash_flow": ["cash_flow"],
}

# Tables that require per-stock iteration
PER_STOCK_TABLES = {"daily_data", "adj_factor", "income_statement", "balance_sheet", "cash_flow"}


def sync_data(
    db_path: str = None,
    provider: str = "tushare",
    start: str = None,
    end: str = None,
    tables: str = "trading_calendar,stock_basic,daily_data,adj_factor",
    symbols: str = None,
    sleep: float = 0.5,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """
    Sync data from a provider into the Open database.

    Args:
        db_path: Path to SQLite database.
        provider: Data provider name (only "tushare" supported).
        start: Start date in YYYYMMDD format.
        end: End date in YYYYMMDD format (defaults to today).
        tables: Comma-separated list of tables to sync.
        symbols: Comma-separated stock codes (e.g. "000001.SZ,600000.SH").
                 If None, syncs all stocks for per-stock tables.
        sleep: Seconds to sleep between Tushare API calls (rate limit).
        dry_run: If True, only validate without writing.
        verbose: Print progress.
    """
    db_path = db_path or DB_PATH
    end = end or datetime.now().strftime("%Y%m%d")
    start = start or DEFAULT_SYNC_START

    if not os.path.exists(db_path):
        print(f"FAIL: Database not found at {db_path}")
        print("Run 'factorfactory init-db' first.")
        sys.exit(1)

    if provider != "tushare":
        print(f"FAIL: Unknown provider '{provider}'. Only 'tushare' is supported.")
        sys.exit(1)

    # Check token - no token should fail immediately with clear message
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        print("FAIL: Missing TUSHARE_TOKEN")
        print("Set TUSHARE_TOKEN environment variable before using sync-data.")
        sys.exit(1)

    # Resolve table aliases
    tables_list = []
    for t in tables.split(","):
        t = t.strip()
        if t not in TABLE_ALIASES:
            print(f"FAIL: Unknown table '{t}'. Valid: {', '.join(sorted(TABLE_ALIASES.keys()))}")
            sys.exit(1)
        tables_list.append(t)

    # Resolve symbols
    symbol_list = None
    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

    print("\nFactorFactory Open - Data Sync")
    print(f"  Provider: {provider}")
    print(f"  Database: {db_path}")
    print(f"  Date range: {start} - {end}")
    print(f"  Tables: {', '.join(tables_list)}")
    if symbol_list:
        print(f"  Symbols: {len(symbol_list)} specified")
    else:
        print("  Symbols: all stocks (from stock_basic)")
    print(f"  Sleep between calls: {sleep}s")
    if dry_run:
        print("  Mode: DRY RUN (no data will be written)")

    # Import provider
    from fundfactory_core.data_providers.tushare_provider import TushareProvider

    try:
        prov = TushareProvider()
    except ValueError as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    total_errors = []

    # --- trading_calendar ---
    if "trading_calendar" in tables_list or "calendar" in tables_list:
        print("\n[1/?] Syncing trading_calendar...")
        try:
            records = prov.fetch_trading_calendar(start, end)
            if dry_run:
                print(f"  DRY RUN: Would insert {len(records)} calendar records")
            else:
                cursor = conn.cursor()
                inserted = 0
                for rec in records:
                    cursor.execute("""
                        INSERT OR REPLACE INTO trading_calendar
                        (trade_date, is_open, day_of_week, week_of_year, month, year, quarter)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (rec["trade_date"], rec["is_open"], rec["day_of_week"],
                          rec["week_of_year"], rec["month"], rec["year"], rec["quarter"]))
                    inserted += 1
                conn.commit()
                print(f"  OK: {inserted} trading_calendar records")
            if verbose:
                print(f"  Sample: {records[0] if records else 'none'}")
        except Exception as e:
            print(f"  FAIL: trading_calendar - {e}")
            total_errors.append(("trading_calendar", str(e)))

    # --- stock_basic ---
    if "stock_basic" in tables_list:
        print("\n[2/?] Syncing stock_basic...")
        try:
            records = prov.fetch_stock_basic()
            if dry_run:
                print(f"  DRY RUN: Would insert {len(records)} stock records")
            else:
                cursor = conn.cursor()
                inserted = 0
                for rec in records:
                    cursor.execute("""
                        INSERT OR REPLACE INTO stock_basic (ts_code, name, list_date)
                        VALUES (?, ?, ?)
                    """, (rec["ts_code"], rec["name"], rec["list_date"]))
                    inserted += 1
                conn.commit()
                print(f"  OK: {inserted} stock_basic records")
            if verbose:
                print(f"  Sample: {records[0] if records else 'none'}")
        except Exception as e:
            print(f"  FAIL: stock_basic - {e}")
            total_errors.append(("stock_basic", str(e)))

    # Get stock list for per-stock tables
    stocks_to_sync = symbol_list
    if not stocks_to_sync and any(t in PER_STOCK_TABLES for t in tables_list):
        # Load from DB if no symbols specified and we need per-stock data
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ts_code FROM stock_basic")
            stocks_to_sync = [row[0] for row in cursor.fetchall()]
            print(f"\n  Loaded {len(stocks_to_sync)} stocks from stock_basic")
        except Exception:
            stocks_to_sync = []

    # --- daily_data ---
    if "daily_data" in tables_list or "daily" in tables_list:
        print("\n[3/?] Syncing daily_data...")
        if not stocks_to_sync:
            print("  SKIP: No stocks available. Run sync with stock_basic first or use --symbols.")
        else:
            total_inserted = 0
            for i, ts_code in enumerate(stocks_to_sync):
                try:
                    records = prov.fetch_daily_data(ts_code, start, end)
                    if not dry_run:
                        cursor = conn.cursor()
                        for rec in records:
                            cursor.execute("""
                                INSERT OR REPLACE INTO daily_data
                                (ts_code, trade_date, open, high, low, close, pre_close,
                                 change, pct_chg, vol, amount)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (rec["ts_code"], rec["trade_date"], rec["open"], rec["high"],
                                  rec["low"], rec["close"], rec["pre_close"], rec["change"],
                                  rec["pct_chg"], rec["vol"], rec["amount"]))
                        conn.commit()
                    total_inserted += len(records)
                    if verbose:
                        print(f"  [{i+1}/{len(stocks_to_sync)}] {ts_code}: {len(records)} records")
                    # Sleep for rate limiting
                    time.sleep(sleep)
                except Exception as e:
                    err_msg = f"{ts_code}: {e}"
                    print(f"  FAIL: daily_data {ts_code} - {e}")
                    total_errors.append(("daily_data", err_msg))
            print(f"  OK: {total_inserted} daily_data records total")

    # --- adj_factor ---
    if "adj_factor" in tables_list:
        print("\n[4/?] Syncing adj_factor...")
        if not stocks_to_sync:
            print("  SKIP: No stocks available. Run sync with stock_basic first or use --symbols.")
        else:
            total_inserted = 0
            for i, ts_code in enumerate(stocks_to_sync):
                try:
                    records = prov.fetch_adj_factor(ts_code, start, end)
                    if not dry_run:
                        cursor = conn.cursor()
                        for rec in records:
                            cursor.execute("""
                                INSERT OR REPLACE INTO adj_factor
                                (ts_code, trade_date, adj_factor)
                                VALUES (?, ?, ?)
                            """, (rec["ts_code"], rec["trade_date"], rec["adj_factor"]))
                        conn.commit()
                    total_inserted += len(records)
                    if verbose:
                        print(f"  [{i+1}/{len(stocks_to_sync)}] {ts_code}: {len(records)} records")
                    time.sleep(sleep)
                except Exception as e:
                    err_msg = f"{ts_code}: {e}"
                    print(f"  FAIL: adj_factor {ts_code} - {e}")
                    total_errors.append(("adj_factor", err_msg))
            print(f"  OK: {total_inserted} adj_factor records total")

    # --- income_statement (skeleton) ---
    if "income_statement" in tables_list or "financial" in tables_list:
        print("\n[5/?] Syncing income_statement...")
        print("  NOTE: income_statement is a skeleton - requires Tushare Pro financial data subscription")
        print("  Financial statement sync requires list_status='P' stocks and periodic (quarterly) fetching")
        print("  To enable: ensure TUSHARE_TOKEN has financial data permissions")
        if not stocks_to_sync:
            print("  SKIP: No stocks available. Run sync with stock_basic first or use --symbols.")
        elif not dry_run:
            total_inserted = 0
            for i, ts_code in enumerate(stocks_to_sync):
                try:
                    records = prov.fetch_income_statement(ts_code, start, end)
                    if records:
                        cursor = conn.cursor()
                        for rec in records:
                            cursor.execute("""
                                INSERT OR REPLACE INTO income_statement
                                (ts_code, ann_date, f_ann_date, end_date, revenue, oper_cost,
                                 sell_exp, admin_exp, fin_exp, rd_exp, operate_profit,
                                 total_profit, income_tax, n_income, n_income_attr_p,
                                 basic_eps, ebit, ebitda, update_flag)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (rec["ts_code"], rec.get("ann_date"), rec.get("f_ann_date"),
                                  rec.get("end_date"), rec.get("revenue"), rec.get("oper_cost"),
                                  rec.get("sell_exp"), rec.get("admin_exp"), rec.get("fin_exp"),
                                  rec.get("rd_exp"), rec.get("operate_profit"), rec.get("total_profit"),
                                  rec.get("income_tax"), rec.get("n_income"), rec.get("n_income_attr_p"),
                                  rec.get("basic_eps"), rec.get("ebit"), rec.get("ebitda"),
                                  rec.get("update_flag")))
                        conn.commit()
                        total_inserted += len(records)
                    time.sleep(sleep)
                except Exception as e:
                    err_msg = f"{ts_code}: {e}"
                    total_errors.append(("income_statement", err_msg))
            print(f"  OK: {total_inserted} income_statement records (may be 0 without Pro data)")

    # --- balance_sheet (skeleton) ---
    if "balance_sheet" in tables_list or "financial" in tables_list:
        print("\n[6/?] Syncing balance_sheet...")
        print("  NOTE: balance_sheet is a skeleton - requires Tushare Pro financial data subscription")
        if not stocks_to_sync:
            print("  SKIP: No stocks available.")
        elif not dry_run:
            total_inserted = 0
            for i, ts_code in enumerate(stocks_to_sync):
                try:
                    records = prov.fetch_balance_sheet(ts_code, start, end)
                    if records:
                        cursor = conn.cursor()
                        for rec in records:
                            cursor.execute("""
                                INSERT OR REPLACE INTO balance_sheet
                                (ts_code, ann_date, f_ann_date, end_date, total_share,
                                 money_cap, accounts_receiv, inventories, total_cur_assets,
                                 total_cur_liab, fix_assets, intan_assets, goodwill,
                                 total_assets, total_liab, st_borr, lt_borr,
                                 total_hldr_eqy_exc_min_int, accounts_pay, update_flag)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (rec["ts_code"], rec.get("ann_date"), rec.get("f_ann_date"),
                                  rec.get("end_date"), rec.get("total_share"), rec.get("money_cap"),
                                  rec.get("accounts_receiv"), rec.get("inventories"),
                                  rec.get("total_cur_assets"), rec.get("total_cur_liab"),
                                  rec.get("fix_assets"), rec.get("intan_assets"), rec.get("goodwill"),
                                  rec.get("total_assets"), rec.get("total_liab"), rec.get("st_borr"),
                                  rec.get("lt_borr"), rec.get("total_hldr_eqy_exc_min_int"),
                                  rec.get("accounts_pay"), rec.get("update_flag")))
                        conn.commit()
                        total_inserted += len(records)
                    time.sleep(sleep)
                except Exception as e:
                    err_msg = f"{ts_code}: {e}"
                    total_errors.append(("balance_sheet", err_msg))
            print(f"  OK: {total_inserted} balance_sheet records (may be 0 without Pro data)")

    # --- cash_flow (skeleton) ---
    if "cash_flow" in tables_list or "financial" in tables_list:
        print("\n[7/?] Syncing cash_flow...")
        print("  NOTE: cash_flow is a skeleton - requires Tushare Pro financial data subscription")
        if not stocks_to_sync:
            print("  SKIP: No stocks available.")
        elif not dry_run:
            total_inserted = 0
            for i, ts_code in enumerate(stocks_to_sync):
                try:
                    records = prov.fetch_cash_flow(ts_code, start, end)
                    if records:
                        cursor = conn.cursor()
                        for rec in records:
                            cursor.execute("""
                                INSERT OR REPLACE INTO cash_flow
                                (ts_code, ann_date, f_ann_date, end_date, net_profit,
                                 c_fr_sale_sg, n_cashflow_act, n_cashflow_inv_act,
                                 free_cashflow, n_cash_flows_fnc_act, update_flag)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (rec["ts_code"], rec.get("ann_date"), rec.get("f_ann_date"),
                                  rec.get("end_date"), rec.get("net_profit"), rec.get("c_fr_sale_sg"),
                                  rec.get("n_cashflow_act"), rec.get("n_cashflow_inv_act"),
                                  rec.get("free_cashflow"), rec.get("n_cash_flows_fnc_act"),
                                  rec.get("update_flag")))
                        conn.commit()
                        total_inserted += len(records)
                    time.sleep(sleep)
                except Exception as e:
                    err_msg = f"{ts_code}: {e}"
                    total_errors.append(("cash_flow", err_msg))
            print(f"  OK: {total_inserted} cash_flow records (may be 0 without Pro data)")

    conn.close()

    print("\n" + "=" * 50)
    if total_errors:
        print(f"  Sync complete with {len(total_errors)} errors:")
        for table, err in total_errors[:10]:
            print(f"    {table}: {err[:80]}")
        if len(total_errors) > 10:
            print(f"    ... and {len(total_errors) - 10} more errors")
    else:
        print("  Sync complete with no errors.")
    print("  Run 'factorfactory check-data' to verify.")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Sync data into FactorFactory Open database")
    parser.add_argument("--db-path", help="Path to SQLite database")
    parser.add_argument("--provider", default="tushare", help="Data provider (default: tushare)")
    parser.add_argument("--start", help="Start date YYYYMMDD (default: 20200101)")
    parser.add_argument("--end", help="End date YYYYMMDD (default: today)")
    parser.add_argument("--tables", default="trading_calendar,stock_basic,daily_data,adj_factor",
                        help="Comma-separated tables to sync")
    parser.add_argument("--symbols", help="Comma-separated stock codes (e.g. 000001.SZ,600000.SH)")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Seconds to sleep between API calls (default: 0.5)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details")
    args = parser.parse_args()

    sync_data(
        db_path=args.db_path,
        provider=args.provider,
        start=args.start,
        end=args.end,
        tables=args.tables,
        symbols=args.symbols,
        sleep=args.sleep,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
