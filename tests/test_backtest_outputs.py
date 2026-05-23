import json

from fundfactory_core.backtest.engine import BacktestConfig, run_backtest
import fundfactory_core.backtest.engine as engine
from tests.test_backtest_engine_basic import _seed_backtest_db


def test_backtest_writes_expected_output_files(tmp_path, monkeypatch):
    db_path = tmp_path / "backtest.db"
    output_dir = tmp_path / "output"
    _seed_backtest_db(db_path)
    monkeypatch.setattr(engine, "DB_PATH", str(db_path))

    result = run_backtest(
        BacktestConfig(
            start_date="20240102",
            end_date="20240104",
            factor_id="MOM_5D",
            top_pct=1.0,
        ),
        output_dir=str(output_dir),
    )

    run_dir = output_dir / f"backtest_{result.run_id}"
    expected = {
        "summary.json",
        "equity_curve.csv",
        "positions.csv",
        "trades.csv",
        "config.json",
    }
    assert expected.issubset({p.name for p in run_dir.iterdir()})

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    for key in [
        "run_id",
        "factor_id",
        "start_date",
        "end_date",
        "benchmark",
        "total_return",
        "annual_return",
        "max_drawdown",
        "sharpe_ratio",
        "volatility",
        "rebalance_count",
        "trade_count",
    ]:
        assert key in summary
    assert summary["factor_id"] == "MOM_5D"

