# FactorFactory Open - 因子工厂开源版

**FactorFactory Open**（因子工厂开源版）是一个完全开源的本地 A 股量化研究底座。目标是为量化研究者、开发者、券商技术团队提供一个可独立运行的数据建库、因子计算和基础回测工具。

- 本地运行，无需账号系统

## 特性

- 数据建库：`init-db` → `sync-data` → `check-data` 完整流程
- Tushare Pro 数据源适配
- 标准 SQLite schema（日线、财务三表、交易日历）
- 98 个内置因子（财务、估值、成长、质量、动量、反转、量价、技术、波动率、流动性等）
- 基础日频回测（CLI + API）
- Broker 接口预留（Paper / QMT 预留）
- 本地运行，无需账号系统

## 快速开始

### 1. 克隆

```bash
git clone <FactorFactory_Open>
cd FactorFactory_Open
```

### 2. 安装依赖

```bash
pip install -r requirements-open.txt
pip install tushare  # 数据源
```

### 3. 配置

```bash
# FUNDAMENTAL: copy .env template to project root
# .env should be placed at PROJECT_ROOT/.env
# (PROJECT_ROOT = parent directory of fundfactory_core/)
cp fundfactory_core/.env.example .env

# 编辑 .env，填入 TUSHARE_TOKEN（从 https://tushare.pro/ 获取）

# 可选：指定自定义项目根目录
export FACTORFACTORY_PROJECT_ROOT=/path/to/your/project
# 可选：指定自定义数据库路径（相对路径基于 PROJECT_ROOT）
export FACTORFACTORY_DB_PATH=data/my_custom.db
```

项目根目录（PROJECT_ROOT）解析规则：
1. `FACTORFACTORY_PROJECT_ROOT` 环境变量（优先）
2. `FUNDFACTORY_PROJECT_ROOT` 环境变量（旧名称兼容）
3. `fundfactory_core/` 的父目录（默认）

路径说明：
- `FACTORFACTORY_DB_PATH` 支持绝对路径或相对于 PROJECT_ROOT 的路径
- `FACTORFACTORY_OUTPUT_DIR` 支持绝对路径或相对于 PROJECT_ROOT 的路径

### 4. 初始化数据库

```bash
python -m fundfactory_core.cli.main init-db
# 或使用便捷命令（如果配置了 PATH）
factorfactory init-db
# 或使用缩写
ff init-db
```

### 5. 同步数据（需要 Tushare Token）

```bash
python -m fundfactory_core.data_pipeline.sync_data \
    --provider tushare \
    --start 20200101 \
    --end 20260520
```

### 6. 检查数据

```bash
python -m fundfactory_core.data_pipeline.check_data
```

### 7. 运行因子

```bash
# 列出可用因子
python -m fundfactory_core.cli.main list-factors

# 计算单个因子
python -m fundfactory_core.cli.main run-factors --factor MOM_20D --date 20260520
```

### 8. 运行回测

```bash
python -m fundfactory_core.cli.main run-backtest \
    --factor MOM_20D \
    --start 20240101 \
    --end 20260520
```

## API 服务器

```bash
python -m fundfactory_core.api.app
# 访问 http://localhost:8001/docs 查看 API 文档
```

## CLI 完整命令

```bash
factorfactory init-db
factorfactory sync-data --provider tushare --start 20200101 --end 20260520
factorfactory check-data
factorfactory list-factors
factorfactory run-factors --factor MOM_20D --date 20260520
factorfactory run-backtest --factor MOM_20D --start 20240101 --end 20260520

# 缩写命令
ff check-data
```

## 数据说明

默认使用用户自己的 `.env` 中的 `TUSHARE_TOKEN` 和本地 SQLite 文件。

不提供真实行情数据。用户需自行准备：

- Tushare Pro API token
- 或兼容 schema 的其他数据源

## 许可证

Apache License 2.0
