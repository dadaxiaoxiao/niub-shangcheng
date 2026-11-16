# Mall

商城领域逻辑与 HTTP API：商品目录（内存数据）+ 会话历史（MySQL 持久化，
SQLAlchemy ORM）。

## 配置

数据库连接只从环境变量读取，代码里没有任何账号密码：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
MALL_DB_URL=mysql://root:password@127.0.0.1:3306/niub_shop
```

- 账号、密码、主机、端口、库名都写在连接串里；密码含 `@ : / #` 等字符时需要 URL 编码。
- 执行初始化命令时会创建库表（账号需要 CREATE 权限）；启动服务只校验，不会建表。
- `MALL_SCHEMA_FILE` 可选，用于指定其他 DDL 文件路径，默认 `schema.sql`。

## 数据库初始化

初始化必须由人主动执行；mall 启动时只校验库表是否存在，不会建库建表。
`schema.sql` 是 DDL 的唯一来源，可重复执行。任选一种方式：

1. **执行初始化命令（不启动 HTTP 服务）**

   ```powershell
   uv run python -m mall.init_db
   ```

2. **手动执行 SQL**

   用任意 MySQL 客户端（mysql CLI、DBX 等）直接执行整个 `schema.sql`。
   文件开头包含 `CREATE DATABASE` 与 `USE`，因此可以脱离应用单独运行。

`init_db` 执行时会跳过文件里的 `CREATE DATABASE` / `USE`，以 `MALL_DB_URL`
中的库名为准。

未初始化时 mall 仍会启动：

- `GET /api/products` 等目录接口正常；
- `GET /api/conversations` 等会话接口返回 503，并带初始化指引；
- `/health` 返回 `"database": "unavailable"`，启动日志会打印初始化命令；
- 初始化完成后不需要重启，下一个请求会重新校验并恢复。

## 数据访问

- 运行期读写使用 SQLAlchemy 2.0 ORM：实体在 `src/mall/entities.py`，
  查询与事务在 `src/mall/conversations.py`。
- ORM 不负责建表，DDL 的唯一来源仍是 `schema.sql`。
- `MALL_DB_URL` 写作 `mysql://...`，代码内部转换为 `mysql+pymysql://`，
  PyMySQL 作为驱动。

## 启动

```powershell
uv run uvicorn mall.main:app --reload --port 3001
```

如果本机 3001 端口被系统保留或占用，可换端口启动，并同步修改
`web/.env.local` 中的 `MALL_API_URL`。

## 接口

- `GET /health`
- `GET /api/products`
- `GET /api/products/{product_id}`
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `GET /api/conversations/{conversation_id}/messages?limit=49`
- `POST /api/conversations/{conversation_id}/messages`
- `DELETE /api/conversations/{conversation_id}`

接口文档：<http://127.0.0.1:3001/docs>