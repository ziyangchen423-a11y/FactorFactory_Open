# 安全说明

## 禁止提交的内容

以下内容**不得**提交到任何公开仓库：

- `.env` 文件（包含真实 token 和密钥）
- `*.db`、`*.sqlite`、`*.sqlite3` 等真实数据库文件
- Tushare token、真实 API 密钥
- 券商账号、服务器密钥
- 私钥内容

## Open 仓库不包含的内容

FactorFactory Open 仓库**不包含**以下内容：

- 账号系统
- 在线服务后台
- 生产部署配置
- 真实密钥或凭证

## 敏感信息检查

提交前建议运行：

```bash
# 检查敏感信息是否泄露
rg -n "password|secret|token|private|key" .

# 检查 .env 是否在忽略列表中
cat .gitignore | grep ".env"
```

## 如发现泄露

若意外提交了敏感信息，请立即：

1. 删除本地提交
2. 修改相关密钥/token
3. 确认无其他泄露内容
