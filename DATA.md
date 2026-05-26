# 数据说明

## 概述

FactorFactory Open 不提供真实数据库。用户使用自己的 Tushare token 同步数据。

## 默认数据库路径

```
data/factorfactory_open.db
```

## 核心表

| 表名 | 说明 | 状态 |
|---|---|---|
| `trading_calendar` | A 股交易日历 | ✅ 完整 |
| `stock_basic` | 股票基本信息 | ✅ 完整 |
| `daily_data` | 日线行情（开盘、收盘、最高、最低、成交量、成交额） | ⚠️ 骨架 |
| `adj_factor` | 复权因子 | ⚠️ 骨架 |
| `income_statement` | 利润表 | ⚠️ 实验性（取决于 Tushare 权限） |
| `balance_sheet` | 资产负债表 | ⚠️ 实验性（取决于 Tushare 权限） |
| `cash_flow` | 现金流量表 | ⚠️ 实验性（取决于 Tushare 权限） |
| `factor_values` | 因子值存储 | ✅ 完整 |
| `backtest_results` | 回测结果 | ✅ 完整 |

> ⚠️ 财务三表（利润表、资产负债表、现金流量表）为实验性功能，需要较高的 Tushare 积分权限。如权限不足，可跳过该数据。

## 数据来源

默认数据源为 [Tushare](https://tushare.pro/)。用户需：

1. 注册 Tushare 账号
2. 获取 token
3. 在 `.env` 中配置 `TUSHARE_TOKEN`

## 因子数据依赖

当前开源版内置 `98` 个因子，按数据依赖分为三类：

| 数据依赖 | 因子类型 | 说明 |
|---|---|---|
| `daily_data` | 动量、反转、技术、波动率、部分量价因子 | 只需要日线行情即可计算 |
| `daily_data + balance_sheet` | 市值、换手率、部分估值因子 | 需要总股本或权益数据 |
| `income_statement + balance_sheet + cash_flow` | 盈利、成长、质量、偿债、运营、费用结构 | 依赖财务三表，受 Tushare 权限和披露完整度影响 |

部分因子在 open schema 下采用明确标注的近似口径：

- `PROF_10`：当前缺少扣非净利润字段，暂以 ROE 近似。
- `GROW_03`：当前缺少扣非净利润字段，暂以归母净利润同比近似。
- `QUAL_06`：当前缺少 `adj_lossgain`，暂以净利润与营业利润差额近似。
- `VALU_05`：当前缺少股息字段，注册为占位因子并返回空结果。

## Tushare 权限不足

部分接口需要较高的 Tushare 积分权限。处理方式：

- **积分不足**：Tushare 对高频调用有限制，降低同步频率或等待配额恢复
- **权限不足**：部分财务数据需要更高的积分，可跳过该数据或手动补充
- **同步失败**：检查网络、Tushare 服务状态、token 是否有效

同步命令示例：

```bash
# 完整同步
factorfactory sync-data --provider tushare --start 20200101

# 指定日期范围
factorfactory sync-data --provider tushare --start 20240101 --end 20241231

# 仅同步交易日历
ff sync-data --provider tushare --tables trading_calendar
```

## 数据检查

```bash
# 检查数据完整性
factorfactory check-data
```
