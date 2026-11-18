# 牛逼商城 (Niub Shangcheng)

一个由三个独立模块组成的最小商城项目：

| 模块 | 职责 | 默认端口 |
| --- | --- | --- |
| `agent-service` | 调用 OpenAI 兼容模型，提供聊天与 SSE HTTP API | `8000` |
| `mall` | 商品目录、会话历史与 HTTP API | `3001` |
| `web` | Next.js 商城页面，并通过服务端代理调用 Agent | `3000` |

依赖方向是 `web -> agent-service` 和 `web -> mall`；`agent-service` 还会通过
HTTP 只读调用 `mall` 的商品目录（当前为 mock 数据）。

> 本机快速启动、实际端口（mall 为 3011）与排障速查见 [reader.md](reader.md)。

## 从零开始：完整运行教程

下面按顺序完成，即可得到一个可逛商品、可多轮对话、可回看历史的本机环境。

### 第 1 步：安装依赖

需要 Python 3.12、Node.js 24、npm 和 MySQL 8.0+。

```powershell
python -m pip install uv
uv sync
Set-Location web
npm install
Set-Location ..
```

> 新克隆的项目没有 `.env`、`config/llm.yaml` 和数据库，后续几步必须手动完成。

### 第 2 步：配置 mall 的数据库连接

```powershell
Copy-Item mall\.env.example mall\.env
```

编辑 `mall\.env`：

```dotenv
MALL_DB_URL=mysql://root:password@127.0.0.1:3306/niub_shop
```

连接串里包含账号、密码、主机、端口和库名；密码含 `@ : / #` 等字符时需要
URL 编码。这个文件已被 gitignore，不会提交到仓库。

### 第 3 步：主动初始化数据库

**mall 启动时只校验库表是否存在，不会自动建库建表**，初始化由你主动执行。
两种方式任选一种：

**方式一：项目命令（推荐）**

```powershell
Set-Location mall
uv run python -m mall.init_db
Set-Location ..
```

预期输出：

```text
数据库已就绪：niub_shop（schema.sql 已应用）
```

命令可以重复执行，已存在的库表不会被改动。初始化需要账号具备 `CREATE`
权限；初始化完成后，运行服务只需要读写权限。

**方式二：手动执行 SQL**

用 mysql CLI、DBX 或任意 MySQL 客户端执行整个 `mall\schema.sql`。
文件开头自带 `CREATE DATABASE` 与 `USE`，可以脱离应用单独运行。
如果连接串用的不是 `niub_shop`，先改掉文件开头那两行。

#### 如果忘记初始化会怎样

mall 仍然会正常启动，只是会话历史不可用：

- 启动日志打印：

  ```text
  ERROR:mall.db:[mall] 数据库不存在：请先执行初始化。
  ERROR:mall.db:[mall] 数据库尚未初始化，会话历史功能不可用。请任选一种方式完成初始化：
    1. 在 mall/.env 配置 MALL_DB_URL，然后在 mall 目录执行：uv run python -m mall.init_db
    2. 用 MySQL 客户端执行 mall/schema.sql
  详见 README 的「从零开始：完整运行教程」。mall 其余接口不受影响。
  ```

- `GET /health` 返回 `"database": "unavailable"`；
- 商品接口 `/api/products` 不受影响；
- 会话接口返回 503，并携带初始化指引；
- 页面 `/chat` 侧栏、`/chat/{id}` 会直接显示初始化命令。

补执行第 3 步后**不需要重启 mall**，下一个请求会自动重新校验并恢复历史功能。

### 第 4 步：配置模型服务

```powershell
Copy-Item agent-service\config\llm.example.yaml agent-service\config\llm.yaml
Copy-Item agent-service\.env.example agent-service\.env
```

编辑 `agent-service\config\llm.yaml`，填入模型服务的 `base_url`、`api_key`
和 `model`：

```yaml
llm:
  base_url: https://api.deepseek.com/v1
  api_key: ${DEEPSEEK_API_KEY}
  model: deepseek-chat
  prompt_file: prompts/shopping_agent.md
  max_turns: 6

mall:
  base_url: http://127.0.0.1:3001
  timeout_seconds: 5
```

- 提示词正文在 `agent-service\prompts\shopping_agent.md`，`prompt_file`
  是它的路径（相对 agent-service 根目录）。修改后下一个请求自动生效。
- `mall.base_url` 指向商品接口，mall 换端口时要同步修改。
- `api_key` 支持 `${ENV_VAR}` 写法，从环境变量读取，避免把密钥写进文件。
- 模板里的占位符不改的话，服务能启动，但聊天会返回 502。
- 配置文件修改后会自动热加载，不需要重启 agent-service。
- 需要使用其他配置文件时，在 `agent-service\.env` 设置 `AGENT_CONFIG_FILE`。

### 第 5 步：配置 web（仅端口与默认值不同时需要）

```powershell
Copy-Item web\.env.example web\.env.local
```

默认值即可：

```dotenv
MALL_API_URL=http://127.0.0.1:3001
AGENT_SERVICE_URL=http://127.0.0.1:8000
```

如果 mall 换了端口（例如本机 3001 被系统保留），必须同步修改
`MALL_API_URL`，否则商品列表和会话历史都不可用。

### 第 6 步：启动三个服务

分别打开三个终端。

商城服务：

```powershell
Set-Location mall
uv run uvicorn mall.main:app --reload --port 3001
```

若本机 3001 端口被系统保留或占用，可换端口启动，并同步修改
`web\.env.local` 中的 `MALL_API_URL`。

Agent 服务：

```powershell
Set-Location agent-service
uv run uvicorn agent_service.main:app --reload --port 8000
```

Web：

```powershell
Set-Location web
npm run dev
```

### 第 7 步：验证

```powershell
curl http://127.0.0.1:3001/health
curl http://127.0.0.1:8000/health
```

期望返回（`model` 和 `mall` 为你配置的值）：

```json
{"status":"ok","service":"mall","database":"ready","database_error":null}
{"status":"ok","service":"agent-service","config_status":"ready","model":"deepseek-chat","mall":"http://127.0.0.1:3001","demo_user_id":"u-demo"}
```

然后按顺序验证功能：

1. 打开 <http://localhost:3000>，能看到 10 件商品；
2. 打开 <http://localhost:3000/chat>，发一条消息，回复逐字流式出现；
3. 刷新页面，消息仍在，左侧出现历史会话；
4. 点击历史会话，地址变为 `/chat/{id}`，内容完整；
5. 在历史会话里继续提问，新消息追加到同一会话；
6. 点侧栏条目的 `×` 删除会话；
7. 问「300 元以内送朋友什么」，回复里的商品、价格和库存来自商城目录，
   不会编造不存在的商品；
8. 问「帮我推荐三个适合送朋友的生日礼物，预算 300 以内」，回复应恰好有
   3 个商品，理由引用浏览/订单/购物车信号；若包含广告商品，名称后带
   「（推广）」。

首页内嵌的问答组件是单轮快速提问，不写入历史；完整多轮对话在 `/chat`。
商城接口文档在 <http://localhost:3001/docs>，Agent 接口文档在
<http://localhost:8000/docs>。

## 常见启动失败

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| mall 日志提示「数据库尚未初始化」，`/health` 的 `database` 为 `unavailable` | 没有执行初始化 | 按第 3 步执行 `mall.init_db` 或 `schema.sql` |
| mall 报 `Access denied` / `Can't connect` | `MALL_DB_URL` 配置错误、密码错或 MySQL 未启动 | 检查连接串和 MySQL 实例；修改 `mall\.env` 后重启 mall |
| 初始化时报 `CREATE DATABASE command denied` | 账号没有建库权限 | 让 DBA 建库，再执行 `schema.sql` 建表 |
| Agent `/health` 返回 `missing_or_invalid` | 缺 `config/llm.yaml` 或校验失败 | 按第 4 步配置 |
| Agent `/health` 的 `prompt` 为 `missing_or_invalid` | 提示词文件缺失、为空或路径错误 | 检查 `llm.prompt_file` 和 `prompts/shopping_agent.md` |
| 聊天返回 502 或 SSE error | `base_url` / `api_key` / `model` 无效 | 检查配置文件，保存后会自动热加载 |
| 首页提示商品未加载、`/chat` 提示历史不可用 | mall 未启动，或端口与 `MALL_API_URL` 不一致 | 先看 mall 健康检查，再改 `web\.env.local` |
| mall 启动提示端口被占用 | 3001 被系统保留或占用 | 换端口启动，并同步修改 `MALL_API_URL` |

## 数据存储

- 商品目录：`mall/src/mall/catalog.py` 中的内存常量。
- 用户画像、浏览/搜索记录、订单、购物车、推荐和广告：`mall/src/mall/personalization.py`
  中的内存 mock，不落库，数据库未初始化时也可用。
- 会话历史：MySQL，DDL 的唯一来源是 `mall/schema.sql`。
- 会话历史的运行期读写通过 SQLAlchemy 2.0 ORM 完成：实体定义在
  `mall/src/mall/entities.py`，查询与事务在 `mall/src/mall/conversations.py`，
  驱动为 PyMySQL。ORM 不负责建表。
- 个性化推荐由 `agent-service` 的 `recommend_products` 工具编排：并行读取画像/
  行为/订单/购物车 → 推荐 mock → 广告 mock → 以目录为准校验过滤 → 模型最终
  选 3 个；工具调用结果不落库。
- Agent 提示词在 `agent-service/prompts/shopping_agent.md`，由
  `config/llm.yaml` 的 `llm.prompt_file` 指定，修改后热加载。
- 初始化只由 `uv run python -m mall.init_db` 或手动执行 `schema.sql` 触发；
  服务启动和运行期只校验，不执行 DDL。
- `init_db` 会跳过 schema 文件里的 `CREATE DATABASE` / `USE`，以
  `MALL_DB_URL` 中的库名为准。
- 会话列表、消息读取与删除都经由 mall 的 `/api/conversations` 接口，
  web 的流式代理负责「读历史 → 调模型 → 写消息」。
- 流式生成中客户端断开时，已生成的部分会以 `interrupted` 状态保存。
- 当前使用固定演示用户 `u-demo`，没有登录和用户切换；所有访客共享同一份
  历史会话和同一份演示画像。

## 个性化推荐链路

`agent-service` 的 `recommend_products` 工具按固定顺序完成：

1. 并行读取用户画像、浏览/搜索记录、历史订单和购物车；
2. 调 mall 推荐 mock 取候选；
3. 调 mall 广告 mock 取推广候选（失败可跳过）；
4. 以商品目录为准校验库存/价格，过滤购物车、退货、avoid、已购耐用品和
   超预算商品；
5. 模型综合画像与候选理由，输出 3 个商品，广告商品标注「（推广）」。

演示用户固定为 `u-demo`，数据在 `mall/src/mall/personalization.py`；可通过
`config/llm.yaml` 的 `mall.demo_user_id` 修改（目前 mock 只有 `u-demo`）。
设计与验收标准见 [spec/personalized-recommendation.md](spec/personalized-recommendation.md)。

## Python 热加载

`uvicorn --reload` 会监听 Python 源文件，文件变化后自动重启 worker。
这属于进程重启，不会保留内存状态。

模型 YAML 配置使用另一种热加载方式：每次聊天请求都会检查文件
`mtime`。配置文件被修改后，下一个请求会自动重新读取并校验配置，
既不需要重启进程，也不会丢失其他请求的内存状态。

## 构建检查

```powershell
uv sync
Set-Location web
npm run build
```

模型调用采用 OpenAI 兼容的 `/chat/completions` 流式协议。