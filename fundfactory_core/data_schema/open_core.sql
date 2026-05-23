-- FactorFactory Open - SQLite Schema
-- This schema defines the minimum tables required for local quantitative research.

-- ============================================================
-- trading_calendar
-- Purpose: All trading day logic must be based on this table.
-- ============================================================
CREATE TABLE IF NOT EXISTS trading_calendar (
    trade_date   TEXT    NOT NULL PRIMARY KEY,
    is_open      INTEGER NOT NULL DEFAULT 1,
    day_of_week  INTEGER,
    week_of_year INTEGER,
    month        INTEGER,
    year         INTEGER,
    quarter      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_calendar_is_open ON trading_calendar(is_open);
CREATE INDEX IF NOT EXISTS idx_calendar_year    ON trading_calendar(year);
CREATE INDEX IF NOT EXISTS idx_calendar_month   ON trading_calendar(month);

-- ============================================================
-- stock_basic
-- Purpose: Stock pool for IPO filtering and ST exclusion.
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code   TEXT    NOT NULL PRIMARY KEY,
    name      TEXT,
    list_date TEXT
);

CREATE INDEX IF NOT EXISTS idx_stock_list_date ON stock_basic(list_date);

-- ============================================================
-- daily_data
-- Purpose: Daily K-line data for price/volume factors and backtesting.
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_data (
    ts_code   TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    pre_close REAL,
    change    REAL,
    pct_chg   REAL,
    vol       REAL,
    amount    REAL,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_trade_date ON daily_data(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_ts_code    ON daily_data(ts_code);

-- ============================================================
-- adj_factor
-- Purpose: Adjustment factor for calculating ex-rights prices.
-- ============================================================
CREATE TABLE IF NOT EXISTS adj_factor (
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    adj_factor  REAL,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_adj_ts_code    ON adj_factor(ts_code);
CREATE INDEX IF NOT EXISTS idx_adj_trade_date ON adj_factor(trade_date);

-- ============================================================
-- income_statement
-- Purpose: Income statement for profitability and growth factors.
-- ============================================================
CREATE TABLE IF NOT EXISTS income_statement (
    ts_code          TEXT,
    ann_date         TEXT,
    f_ann_date       TEXT,
    end_date         TEXT,
    revenue          REAL,
    oper_cost        REAL,
    sell_exp         REAL,
    admin_exp        REAL,
    fin_exp          REAL,
    rd_exp           REAL,
    operate_profit   REAL,
    total_profit     REAL,
    income_tax       REAL,
    n_income         REAL,
    n_income_attr_p  REAL,
    basic_eps        REAL,
    ebit             REAL,
    ebitda           REAL,
    update_flag      TEXT,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_income_end_date  ON income_statement(end_date);
CREATE INDEX IF NOT EXISTS idx_income_ann_date  ON income_statement(ann_date);
CREATE INDEX IF NOT EXISTS idx_income_ts_code    ON income_statement(ts_code);

-- ============================================================
-- balance_sheet
-- Purpose: Balance sheet for valuation and solvency factors.
-- ============================================================
CREATE TABLE IF NOT EXISTS balance_sheet (
    ts_code                       TEXT,
    ann_date                      TEXT,
    f_ann_date                    TEXT,
    end_date                      TEXT,
    total_share                   REAL,
    money_cap                     REAL,
    accounts_receiv               REAL,
    inventories                   REAL,
    total_cur_assets              REAL,
    total_cur_liab               REAL,
    fix_assets                    REAL,
    intan_assets                  REAL,
    goodwill                      REAL,
    total_assets                  REAL,
    total_liab                    REAL,
    st_borr                       REAL,
    lt_borr                       REAL,
    total_hldr_eqy_exc_min_int    REAL,
    accounts_pay                  REAL,
    update_flag                   TEXT,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_balance_end_date  ON balance_sheet(end_date);
CREATE INDEX IF NOT EXISTS idx_balance_ann_date   ON balance_sheet(ann_date);
CREATE INDEX IF NOT EXISTS idx_balance_ts_code    ON balance_sheet(ts_code);

-- ============================================================
-- cash_flow
-- Purpose: Cash flow statement for cash quality factors.
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_flow (
    ts_code             TEXT,
    ann_date            TEXT,
    f_ann_date          TEXT,
    end_date            TEXT,
    net_profit          REAL,
    c_fr_sale_sg        REAL,
    n_cashflow_act      REAL,
    n_cashflow_inv_act  REAL,
    free_cashflow       REAL,
    n_cash_flows_fnc_act REAL,
    update_flag         TEXT,
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_cashflow_end_date ON cash_flow(end_date);
CREATE INDEX IF NOT EXISTS idx_cashflow_ann_date  ON cash_flow(ann_date);
CREATE INDEX IF NOT EXISTS idx_cashflow_ts_code   ON cash_flow(ts_code);

-- ============================================================
-- factor_values
-- Purpose: Store computed factor values for backtesting.
-- ============================================================
CREATE TABLE IF NOT EXISTS factor_values (
    factor_id    TEXT    NOT NULL,
    calc_date    TEXT    NOT NULL,
    ts_code      TEXT    NOT NULL,
    factor_value REAL,
    rank_value   REAL,
    category     TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (factor_id, calc_date, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_fv_calc_date  ON factor_values(calc_date);
CREATE INDEX IF NOT EXISTS idx_fv_ts_code     ON factor_values(ts_code);
CREATE INDEX IF NOT EXISTS idx_fv_factor_id   ON factor_values(factor_id);

-- ============================================================
-- backtest_results
-- Purpose: Store backtest run summaries.
-- ============================================================
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id        TEXT    NOT NULL PRIMARY KEY,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    start_date    TEXT,
    end_date      TEXT,
    factor_id     TEXT,
    benchmark     TEXT,
    total_return  REAL,
    annual_return REAL,
    max_drawdown  REAL,
    sharpe_ratio  REAL,
    volatility    REAL,
    params        TEXT,
    summary_path  TEXT
);

CREATE INDEX IF NOT EXISTS idx_bt_created  ON backtest_results(created_at);
CREATE INDEX IF NOT EXISTS idx_bt_factor   ON backtest_results(factor_id);
