"""
FastAPI application for FactorFactory Open.

Provides local-only API endpoints for:
- Health check
- Data status
- Factor listing and calculation
- Backtest running and results

No authentication, no payment, no user management.
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure fundfactory_core is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fundfactory_core.config.settings import DB_PATH, settings
from fundfactory_core.factors.registry import factor_ids, get_all_metadata
from fundfactory_core.backtest.engine import BacktestConfig, run_backtest

app = FastAPI(
    title="FactorFactory Open API",
    description="Local quantitative research API - no authentication required",
    version="0.1.0",
)

# CORS - allow all local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Models ====================

class FactorRunRequest(BaseModel):
    factor_ids: list[str]
    start_date: str
    end_date: str


class BacktestRequest(BaseModel):
    factor_id: str
    start_date: str
    end_date: str
    benchmark: str = "000300.SH"
    rebalance_freq: int = 20
    top_pct: float = 0.1
    initial_cash: float = 1000000
    fee_rate: float = 0.0003
    slippage_rate: float = 0.0005


# ==================== Health ====================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
    }


# ==================== Data Status ====================

@app.get("/data/status")
def data_status():
    import sqlite3
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Database not initialized. Run fundfactory init-db first.")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()
    tables = ["trading_calendar", "stock_basic", "daily_data", "income_statement", "balance_sheet", "cash_flow"]
    status = {}
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        status[t] = cursor.fetchone()[0]
    cursor.execute("SELECT MAX(trade_date) FROM trading_calendar WHERE is_open = 1")
    latest_date = cursor.fetchone()[0]
    conn.close()
    return {"db_path": DB_PATH, "tables": status, "latest_trading_date": latest_date}


# ==================== Factors ====================

@app.get("/factors")
def list_factors():
    """List all available factors."""
    meta = get_all_metadata()
    return {"count": len(meta), "factors": meta}


@app.post("/factors/run")
def run_factors(req: FactorRunRequest):
    """Run factor calculation for specified factors and date range."""
    import sqlite3
    from fundfactory_core.factors.registry import get_calc_func

    results = {}
    for fid in req.factor_ids:
        calc_func = get_calc_func(fid)
        if not calc_func:
            results[fid] = {"status": "error", "message": f"Unknown factor: {fid}"}
            continue

        try:
            # Write factor values to database
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            written = 0
            for date in _date_range(req.start_date, req.end_date):
                df = calc_func(date)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        cursor.execute("""
                            INSERT OR REPLACE INTO factor_values
                            (factor_id, calc_date, ts_code, factor_value, rank_value, category)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            fid, date, row["ts_code"], row.get("factor_value"),
                            row.get("rank_value"), row.get("category")
                        ))
                        written += 1
            conn.commit()
            conn.close()
            results[fid] = {"status": "ok", "written": written}
        except Exception as e:
            results[fid] = {"status": "error", "message": str(e)}

    return results


# ==================== Backtest ====================

@app.post("/backtest/run")
def run_backtest_api(req: BacktestRequest):
    """Run a backtest with the specified parameters."""
    config = BacktestConfig(
        start_date=req.start_date,
        end_date=req.end_date,
        factor_id=req.factor_id,
        benchmark=req.benchmark,
        rebalance_freq=req.rebalance_freq,
        top_pct=req.top_pct,
        initial_cash=req.initial_cash,
        fee_rate=req.fee_rate,
        slippage_rate=req.slippage_rate,
    )
    result = run_backtest(config)
    return {
        "run_id": result.run_id,
        "metrics": {
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "volatility": result.volatility,
        },
        "summary_path": f"output/backtest_{result.run_id}/summary.json",
    }


@app.get("/backtest/results/{run_id}")
def get_backtest_results(run_id: str):
    """Get backtest result summary."""
    import json
    summary_path = Path(settings.OUTPUT_DIR) / f"backtest_{run_id}" / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")
    with open(summary_path) as f:
        return json.load(f)


# ==================== Utilities ====================

def _date_range(start: str, end: str):
    """Yield dates in range YYYYMMDD."""
    from datetime import datetime, timedelta
    dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    while dt <= end_dt:
        yield dt.strftime("%Y%m%d")
        dt += timedelta(days=1)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
