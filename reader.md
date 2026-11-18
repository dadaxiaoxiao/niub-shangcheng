# 快速启动手册

给本机开发和自动化 Agent 用的最短路径。完整教程、功能验证清单见 [README.md](README.md)。

## 本机约定

| 模块 | 目录 | 端口 | 启动命令 |
| --- | --- | --- | --- |
| mall（商品 + 会话 API） | `mall/` | **3011** | `uv run uvicorn mall.main:app --reload --port 3011` |
| agent-service（模型 + SSE） | `agent-service/` | 8000 | `uv run uvicorn agent_service.main:app --reload --port 8000` |
| web（Next.js 页面） | `web/` | 3000 | `npm run dev` |

> 3001 在本机被系统进程占用（PID 4），所以 mall 固定用 **3011**。
> `web/.env.local` 的 `MALL_API_URL` 和 `agent-service/config/llm.yaml`
> 的 `mall.base_url` 必须同时指向 `http://127.0.0.1:3011`。
> 换端口时这两个文件要一起改。

## 第 0 步：先确认是否已经在运行

**不要先启动**，先探活。三个都健康就直接用，重复启动只会端口冲突。

```bash
curl -s http://127.0.0.1:3011/health   # mall
curl -s http://127.0.0.1:8000/health   # agent
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/   # web
```

期望结果：

```json
{"status":"ok","service":"mall","database":"ready","database_error":null}
{"status":"ok","service":"agent-service","config_status":"ready","model":"deepseek-chat","mall":"http://127.0.0.1:3011","demo_user_id":"u-demo","prompt":"ready"}
```

web 返回 `200`。健康时的入口：

- 首页 <http://localhost:3000>
- 多轮对话 <http://localhost:3000/chat>
- mall 文档 <http://127.0.0.1:3011/docs>
- agent 文档 <http://127.0.0.1:8000/docs>

查看端口占用（Git Bash）：

```bash
netstat -ano | grep -E ":(3000|3011|8000)\s" | grep LISTENING
```

## 第 1 步：首次准备（已配好可跳过）

```bash
uv sync
cd web && npm install && cd ..

# 配置文件：mall/.env、agent-service/.env、agent-service/config/llm.yaml、web/.env.local
# 数据库只需初始化一次（要求 MySQL 已在 3306 运行）
cd mall && uv run python -m mall.init_db && cd ..
```

`mall.init_db` 可重复执行；mall 启动时只校验表是否存在，不会自动建表。

## 第 2 步：按顺序启动（三个终端，均在仓库根目录执行）

终端 1：mall

```bash
cd mall
uv run uvicorn mall.main:app --reload --port 3011
```

终端 2：agent-service

```bash
cd agent-service
uv run uvicorn agent_service.main:app --reload --port 8000
```

终端 3：web

```bash
cd web
npm run dev
```

顺序原因：web 首次渲染会请求 mall 的商品和会话；agent 处理聊天时会回查 mall。

## 第 3 步：验证

```bash
curl -s http://127.0.0.1:3011/health
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:3011/api/products | head -c 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/chat
```

个性化推荐相关接口（演示用户 `u-demo`）：

```bash
curl -s http://127.0.0.1:3011/api/users/u-demo/profile
curl -s http://127.0.0.1:3011/api/users/u-demo/browsing-history
curl -s http://127.0.0.1:3011/api/users/u-demo/orders
curl -s http://127.0.0.1:3011/api/users/u-demo/cart
curl -s "http://127.0.0.1:3011/api/recommendations/u-demo?limit=10" | head -c 400
curl -s "http://127.0.0.1:3011/api/ads/candidates?user_id=u-demo&context_product_ids=jasmine-tea&limit=3" | head -c 400
```

聊天里问「帮我推荐三个适合送朋友的生日礼物，预算 300 以内」，应返回 3 个
商品；如果包含广告商品，名称后应有「（推广）」，推荐理由会引用浏览、订单或
购物车信号。详细设计见 [spec/personalized-recommendation.md](spec/personalized-recommendation.md)。

## 停止 / 重启

```bash
# 按 PID 结束（PID 来自 netstat 输出）
taskkill //PID <pid> //F
```

改动 Python 代码不需要手动重启，`--reload` 会处理；改 YAML / 提示词会在下一个请求热加载；
改 `.env`、`.env.local` 需要重启对应服务；改 `web` 的 `next.config` 需要重启 `npm run dev`。

## 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 启动报 `[Errno 10048]` / 端口占用 | 服务已在跑或端口被保留 | 先探活；3001 被系统占用，mall 用 3011 |
| mall `/health` 的 `database` 为 `unavailable` | 未初始化库表或 `MALL_DB_URL` 错 | 执行 `cd mall && uv run python -m mall.init_db` |
| mall 报 `Access denied` / `Can't connect` | MySQL 未启动、密码错 | 启动 MySQL，检查 `mall/.env` 后重启 mall |
| agent `/health` 为 `missing_or_invalid` | 缺 `config/llm.yaml` 或 `api_key` 占位符未改 | 从 `llm.example.yaml` 复制并填写，保存后自动热加载 |
| 页面提示商品/历史不可用 | mall 没起，或 `MALL_API_URL` 端口不一致 | 先查 mall 健康检查，再改 `web/.env.local` |
| 聊天 502 / SSE error | `base_url`、`api_key`、`model` 无效 | 检查 `agent-service/config/llm.yaml` |