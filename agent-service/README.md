# Agent Service

基于 OpenAI 兼容接口的真实模型流式服务。

```powershell
Copy-Item config.example.yaml config.yaml
Copy-Item .env.example .env
uv run uvicorn agent_service.main:app --reload --port 8000
```

编辑 `config.yaml` 填写 `base_url`、`api_key`、`model`。配置在下一个请求
自动热加载。

- `GET /health`
- `POST /api/chat`，单轮非流式聊天
- `POST /api/chat/stream`，多轮 SSE 流式聊天

