"""
Init DB command - creates the Open core database schema.

Usage:
    python -m fundfactory_core.data_pipeline.init_db
    factorfactory init-db
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Add parent to path for imports when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fundfactory_core.config.settings import DB_PATH


def get_schema_sql() -> str:
    """Return the full schema SQL."""
    schema_path = Path(__file__).parent.parent / "data_schema" / "open_core.sql"
    return schema_path.read_text()


def split_sql_statements(sql_text: str) -> list[str]:
    """
    Split SQL text into individual statements, handling multi-line statements
    and ignoring line comments.
    """
    # Remove line comments (-- ...)
    lines = []
    for line in sql_text.splitlines():
        # Find -- comment start, but not inside quotes
        in_single = False
        in_double = False
        idx = 0
        while idx < len(line):
            c = line[idx]
            if c == "'" and not in_double:
                in_single = not in_single
            elif c == '"' and not in_single:
                in_double = not in_double
            elif c == '-' and idx + 1 < len(line) and line[idx + 1] == '-' and not in_single and not in_double:
                break  # rest of line is comment
            idx += 1
        lines.append(line[:idx])
    sql_text = '\n'.join(lines)

    # Split on semicolon, filter empty
    statements = []
    for stmt in sql_text.split(';'):
        stmt = stmt.strip()
        if stmt:
            statements.append(stmt)
    return statements


def init_db(db_path: str = None, *, verbose: bool = False) -> None:
    """
    Initialize the Open core database.

    Creates all required tables and indices.
    Safe to run multiple times - uses CREATE TABLE IF NOT EXISTS.

    Args:
        db_path: Path to SQLite database. Defaults to settings.DB_PATH.
        verbose: Print each table creation result.
    """
    db_path = db_path or DB_PATH

    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    schema_sql = get_schema_sql()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    statements = split_sql_statements(schema_sql)

    tables_created = []
    for stmt in statements:
        if stmt:
            try:
                cursor.execute(stmt)
                # Try to extract table name from statement
                upper = stmt.upper()
                if "CREATE TABLE" in upper:
                    # Get table name
                    parts = upper.split("CREATE TABLE")
                    if len(parts) > 1:
                        name_part = parts[1].strip()
                        if name_part.startswith("IF NOT EXISTS"):
                            name_part = name_part[len("IF NOT EXISTS"):].strip()
                        table_name = name_part.split()[0].strip('"[]`')
                        tables_created.append(table_name)
                        if verbose:
                            print(f"  OK: {table_name}")
            except sqlite3.Error as e:
                print(f"  FAIL: {stmt[:60]}... -> {e}", file=sys.stderr)

    conn.commit()
    conn.close()

    print(f"\nFactorFactory Open database initialized at:\n  {db_path}")
    print(f"Tables: {len(tables_created)}")
    if verbose:
        for t in tables_created:
            print(f"  - {t}")
    print("\nNext: run 'factorfactory sync-data --provider tushare --start 20200101' to fetch data.")


def main():
    parser = argparse.ArgumentParser(description="Initialize FactorFactory Open database")
    parser.add_argument("--db-path", help="Path to SQLite database (default: from settings)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details")
    args = parser.parse_args()

    init_db(db_path=args.db_path, verbose=args.verbose)


if __name__ == "__main__":
    main()
