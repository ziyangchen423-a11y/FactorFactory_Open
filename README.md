<!--
╔══════════════════════════════════════════════════════════════════════╗
║  DreamSeed 种梦计划 — AI创造者大赛  官方 README 模板                ║
║                                                                      ║
║  使用说明：                                                          ║
║  1. 将本模板放在参赛仓库根目录 README.md 的顶部                       ║
║  2. 头图使用 DreamField 官方公开活动图片地址                         ║
║  3. 请保留 DREAMFIELD_README_HEADER_START / END 标识                 ║
║  4. 分割线以下供创作者自由编写项目内容                               ║
╚══════════════════════════════════════════════════════════════════════╝
-->

<!-- DREAMFIELD_README_HEADER_START -->

<p align="center">
  <a href="https://www.dreamfield.top">
    <img src="https://www.dreamfield.top/dream-field/contest-readme/assets/dreamseed-readme-banner.png" alt="DreamSeed 种梦计划参赛作品" width="100%" />
  </a>
</p>

<!-- DREAMFIELD_README_HEADER_END -->

# FactorFactory Open - 因子工厂开源版

## What it is

FactorFactory Open（因子工厂开源版）是本地 A 股量化研究底座 Alpha 版，提供因子计算、数据同步和基础回测能力。

## What is included

- **98 个内置因子**：覆盖财务、估值、成长、盈利质量、偿债、运营效率、费用结构、动量、反转、量价、技术、波动率和流动性
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
factorfactory init-db

# 5. 检查数据完整性
factorfactory check-data

# 6. 查看可用因子
factorfactory list-factors

# 7. 同步数据（可选，从 Tushare 拉取）
factorfactory sync-data \
  --provider tushare \
  --start 20240101 \
  --end 20240131 \
  --tables trading_calendar,stock_basic,daily_data,adj_factor \
  --symbols 000001.SZ,600000.SH \
  --sleep 0.5

# 8. 运行因子计算
factorfactory run-factors --factor MOM_20D --date 20260520

# 9. 运行回测
factorfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520
```

也可以使用缩写命令 `ff`，例如：`ff check-data`。

## Run factors

```bash
factorfactory run-factors --factor MOM_20D --date 20260520
```

## Built-in factors

当前开源版注册 `98` 个因子：

| 类别 | 数量 | 示例 |
|---|---:|---|
| 动量/收益 | 13 | `MOM_20D`, `MOM_120D`, `RET_20D`, `WEIGHTED_MOM_20D` |
| 盈利能力 | 12 | `ROE`, `ROA`, `PROF_01`, `PROF_04` |
| 波动/风险 | 10 | `VOL_20D`, `ATR_20D`, `DOWNSIDE_VOL_20D` |
| 成长能力 | 8 | `GROW_01`, `GROW_02`, `GROW_08` |
| 偿债/杠杆 | 8 | `DEBT_01`, `DEBT_02`, `DEBT_05` |
| 运营效率 | 8 | `OPER_01`, `OPER_02`, `OPER_05` |
| 估值 | 7 | `PE_SIMPLE`, `PB_SIMPLE`, `VALU_01`, `VALU_04` |
| 盈利质量 | 7 | `QUAL_01`, `QUAL_04`, `QUAL_05` |
| 技术指标 | 6 | `MA_DEV_20D`, `RSI_20D`, `WILLIAMS_R_20D` |
| 成交量/额 | 5 | `VOL_RATIO_20D`, `AMOUNT_RATIO_20D` |
| 费用结构 | 5 | `EXP_01`, `EXP_04`, `EXP_05` |
| 其他 | 9 | 规模、流动性、反转、彩票效应等 |

其中 `VALU_05` 为股息率占位因子：当前 open schema 尚无股息字段，已注册但会返回空结果，避免伪造数据。`PROF_10`、`GROW_03`、`QUAL_06` 是 open schema 下的近似口径，metadata 中有说明。

## Run backtest

```bash
factorfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520
```

## Roadmap

- [ ] 扩展因子库（价值、情绪、技术面因子）
- [ ] 完善财务三表数据同步
- [ ] 多因子组合回测支持
- [ ] 参数优化框架
- [ ] 社区贡献因子审核流程

## License

Apache License 2.0. See [LICENSE](LICENSE) file.
