# FactorFactory Open - 因子工厂开源版

## What it is

FactorFactory Open（因子工厂开源版）是本地 A 股量化研究底座 Alpha 版，提供因子计算、数据同步和基础回测能力。

## What is included

- **10 个示例因子**：动量、波动率、估值等基础因子
- **数据同步**：支持 Tushare 接口同步交易日历、股票基本信息、日线行情、复权因子
- **因子计算**：CLI 命令计算因子值并存入本地 SQLite 数据库
- **基础回测**：支持单因子分层回测，输出收益率、最大回撤、夏普比率等指标
- **CLI 工具**：完整的命令行工具（init-db、check-data、sync-data、list-factors、run-factors、run-backtest）

## What is not included

- 不提供真实数据库（用户自备 Tushare token）
- 不包含账号系统或在线服务后台
- 不包含生产部署配置
- 不包含真实券商交易功能

## Quick start

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -e .

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 Tushare token

# 4. 初始化数据库
fundfactory init-db

# 5. 检查数据完整性
fundfactory check-data

# 6. 查看可用因子
fundfactory list-factors

# 7. 同步数据（可选，从 Tushare 拉取）
fundfactory sync-data \
  --provider tushare \
  --start 20240101 \
  --end 20240131 \
  --tables trading_calendar,stock_basic,daily_data,adj_factor \
  --symbols 000001.SZ,600000.SH \
  --sleep 0.5

# 8. 运行因子计算
fundfactory run-factors --factor MOM_20D --date 20260520

# 9. 运行回测
fundfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520
```

## Run factors

```bash
fundfactory run-factors --factor MOM_20D --date 20260520
```

## Run backtest

```bash
fundfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520
```

## Roadmap

- [ ] 扩展因子库（价值、情绪、技术面因子）
- [ ] 完善财务三表数据同步
- [ ] 多因子组合回测支持
- [ ] 参数优化框架
- [ ] 社区贡献因子审核流程

## License

See [LICENSE](LICENSE) file.
