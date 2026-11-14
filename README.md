# Niub Shangcheng

一个由三个独立模块组成的最小商城项目：

| 模块 | 职责 | 默认端口 |
| --- | --- | --- |
| `agent-service` | 调用 OpenAI 兼容模型，提供聊天与 SSE HTTP API | `8000` |
| `mall` | 商城领域逻辑、商品目录与 HTTP API | `3001` |
| `web` | Next.js 商城页面，并通过服务端代理调用 Agent | `3000` |

依赖方向是 `web -> agent-service` 和 `web -> mall`。商城和 Agent 服务之间没有直接依赖。

## 初始化

需要 Python 3.12、Node.js 24 和 npm。

```powershell
python -m pip install uv
uv sync
Copy-Item agent-service\config.example.yaml agent-service\config.yaml
Copy-Item agent-service\.env.example agent-service\.env
Copy-Item web\.env.example web\.env.local
```

编辑 `agent-service\config.yaml`，填入模型服务的 `base_url`、`api_key`
和 `model`。如果需要使用其他配置文件，在 `agent-service\.env` 中设置：

```dotenv
AGENT_CONFIG_FILE=D:\path\to\model-config.yaml
```

相对路径以 Agent 服务当前工作目录为准。`api_key` 也可以写成
`${OPENAI_API_KEY}`，从环境变量读取。

```powershell
Set-Location web
npm install
Set-Location ..
```

## 启动

分别打开三个终端。

商城服务：

```powershell
Set-Location mall
uv run uvicorn mall.main:app --reload --port 3001
```

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

打开 <http://localhost:3000>。完整的多轮对话页面位于
<http://localhost:3000/chat>，页面通过 SSE 接收真实模型的流式回复。
商城接口文档位于
<http://localhost:3001/docs>，Agent 接口文档位于
<http://localhost:8000/docs>。

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

