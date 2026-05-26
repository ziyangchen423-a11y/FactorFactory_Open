"""
FactorFactory Open CLI entry point.

Usage:
    factorfactory init-db
    factorfactory sync-data --provider tushare --start 20200101
    factorfactory check-data
    factorfactory run-factors --factor MOM_20D --date 20260520
    factorfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520

Short alias:
    ff check-data
"""
import argparse
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fundfactory_core.config.settings import DB_PATH as _SETTINGS_DB_PATH  # noqa: F401


def cmd_init_db(args):
    from fundfactory_core.data_pipeline.init_db import init_db
    init_db(db_path=args.db_path, verbose=args.verbose)


def cmd_check_data(args):
    from fundfactory_core.data_pipeline.check_data import check_data
    check_data(db_path=args.db_path, verbose=args.verbose)


def cmd_sync_data(args):
    from fundfactory_core.data_pipeline.sync_data import sync_data
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


def cmd_list_factors(args):
    from fundfactory_core.factors.registry import get_all_metadata
    meta = get_all_metadata()
    print(f"\nAvailable factors ({len(meta)}):")
    for fid, m in meta.items():
        print(f"  {fid:20s} [{m.get('category', '?'):15s}] {m.get('name', '')}")


def cmd_run_factors(args):
    from fundfactory_core.factors.registry import factor_ids, get_calc_func
    import sqlite3
    from fundfactory_core.config.settings import DB_PATH

    if not args.factor:
        print("FAIL: --factor is required")
        sys.exit(1)
    if not args.date:
        print("FAIL: --date is required (YYYYMMDD)")
        sys.exit(1)

    calc_func = get_calc_func(args.factor)
    if not calc_func:
        print(f"FAIL: Unknown factor: {args.factor}")
        print(f"Available: {', '.join(factor_ids())}")
        sys.exit(1)

    print(f"\nRunning factor: {args.factor}")
    print(f"  Date: {args.date}")

    try:
        df = calc_func(args.date)
        if df is None or df.empty:
            print("  No data returned")
        else:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            written = 0
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO factor_values
                    (factor_id, calc_date, ts_code, factor_value, rank_value, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    args.factor, args.date, row["ts_code"],
                    row.get("factor_value"), row.get("rank_value"),
                    row.get("category")
                ))
                written += 1
            conn.commit()
            conn.close()
            print(f"  OK: {written} values written to factor_values table")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)


def cmd_run_backtest(args):
    from fundfactory_core.backtest.engine import BacktestConfig, run_backtest

    if not args.factor:
        print("FAIL: --factor is required")
        sys.exit(1)
    start = args.start or "20240101"
    end = args.end or "20260520"

    config = BacktestConfig(
        start_date=start,
        end_date=end,
        factor_id=args.factor,
        benchmark=args.benchmark or "000300.SH",
        rebalance_freq=args.rebalance_freq or 20,
        top_pct=args.top_pct or 0.1,
        initial_cash=args.initial_cash or 1000000,
        fee_rate=args.fee_rate or 0.0003,
        slippage_rate=args.slippage or 0.0005,
    )

    print("\nRunning backtest:")
    print(f"  Factor: {config.factor_id}")
    print(f"  Period: {config.start_date} - {config.end_date}")
    print(f"  Benchmark: {config.benchmark}")

    try:
        result = run_backtest(config)
        print("\n  Summary:")
        print(f"    Total Return:   {result.total_return:.2f}%")
        print(f"    Annual Return:  {result.annual_return:.2f}%")
        print(f"    Max Drawdown:   {result.max_drawdown:.2f}%")
        print(f"    Sharpe Ratio:   {result.sharpe_ratio:.2f}")
        print(f"    Volatility:     {result.volatility:.2f}%")
        print(f"\n  Output: output/backtest_{result.run_id}/")
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="FactorFactory Open CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  factorfactory init-db
  factorfactory sync-data --provider tushare --start 20200101
  factorfactory check-data
  factorfactory list-factors
  factorfactory run-factors --factor MOM_20D --date 20260520
  factorfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520
  ff check-data
        """
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init-db
    p = sub.add_parser("init-db", help="Initialize the database schema")
    p.add_argument("--db-path", help="Path to SQLite database")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_init_db)

    # check-data
    p = sub.add_parser("check-data", help="Check database status")
    p.add_argument("--db-path", help="Path to SQLite database")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_check_data)

    # sync-data
    p = sub.add_parser("sync-data", help="Sync data from provider")
    p.add_argument("--db-path", help="Path to SQLite database")
    p.add_argument("--provider", default="tushare", help="Provider name (default: tushare)")
    p.add_argument("--start", help="Start date YYYYMMDD")
    p.add_argument("--end", help="End date YYYYMMDD")
    p.add_argument("--tables", default="trading_calendar,stock_basic,daily_data,adj_factor",
                   help="Tables to sync")
    p.add_argument("--symbols", help="Comma-separated stock codes (e.g. 000001.SZ,600000.SH)")
    p.add_argument("--sleep", type=float, default=0.5,
                   help="Seconds between API calls (default: 0.5)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_sync_data)

    # list-factors
    p = sub.add_parser("list-factors", help="List available factors")
    p.set_defaults(func=cmd_list_factors)

    # run-factors
    p = sub.add_parser("run-factors", help="Run factor calculation")
    p.add_argument("--factor", required=True, help="Factor ID")
    p.add_argument("--date", required=True, help="Calculation date YYYYMMDD")
    p.set_defaults(func=cmd_run_factors)

    # run-backtest
    p = sub.add_parser("run-backtest", help="Run backtest")
    p.add_argument("--factor", required=True, help="Factor ID")
    p.add_argument("--start", help="Start date YYYYMMDD (default: 20240101)")
    p.add_argument("--end", help="End date YYYYMMDD (default: 20260520)")
    p.add_argument("--benchmark", help="Benchmark code (default: 000300.SH)")
    p.add_argument("--rebalance-freq", type=int, help="Rebalance frequency in trading days")
    p.add_argument("--top-pct", type=float, help="Top percentage of stocks (e.g. 0.1 for 10%%)")
    p.add_argument("--initial-cash", type=float, help="Initial cash amount")
    p.add_argument("--fee-rate", type=float, help="Fee rate (default: 0.0003)")
    p.add_argument("--slippage", type=float, help="Slippage rate (default: 0.0005)")
    p.set_defaults(func=cmd_run_backtest)

    args = parser.parse_args()

    # Handle convenience top-level commands (backtest as alias)
    if args.command == "backtest":
        args.command = "run-backtest"

    args.func(args)


if __name__ == "__main__":
    main()
