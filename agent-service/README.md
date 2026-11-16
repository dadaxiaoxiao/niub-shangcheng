# Agent Service

基于 OpenAI 兼容接口的模型服务，使用 OpenAI Agents SDK 构建 ReAct 循环，
支持流式聊天和商品推荐工具。

## 启动

```powershell
Copy-Item config\llm.example.yaml config\llm.yaml
Copy-Item .env.example .env
uv run uvicorn agent_service.main:app --reload --port 8000
```

编辑 `config/llm.yaml` 填写模型与商城的连接信息。配置在下一个请求自动热加载。

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

- `mall.base_url` 指向 mall 的商品接口，默认 `http://127.0.0.1:3001`；
  mall 换端口时要同步修改。
- `llm.max_turns` 控制 Agent SDK 的最大轮次，默认 6；超出时返回明确提示。

## 提示词

提示词正文在 `prompts/shopping_agent.md`，由 `llm.prompt_file` 指定：

- 相对路径以 agent-service 根目录为基准，绝对路径原样使用。
- 修改文件后下一个请求自动重新读取，不需要重启。
- 文件缺失、为空或不可读时，`/health` 的 `prompt` 为 `missing_or_invalid`，
  聊天接口返回 503。
- 旧配置里的 `llm.system_prompt` 会报迁移错误，需要把内容移到提示词文件。

## 商品推荐工具

模型通过 function calling 自主调用两个工具：

| 工具 | 作用 |
| --- | --- |
| `search_products` | 按关键词、品类、最高价格和库存筛选商品，返回真实价格与库存 |
| `get_product` | 按商品 ID 获取详情 |

- 商品数据来自 mall 的 `GET /api/products`（当前为内存 mock），
  一次聊天请求内缓存，只读。
- 提示词要求模型「先查后答」：只推荐工具返回的商品，不编造价格和库存。
- 查询为空时工具结果会附带 `hint`，引导模型放宽关键词或改用具体品类。
- 工具参数用 Pydantic 校验，`limit` 限制在 1–10。
- ReAct 循环由 OpenAI Agents SDK 的 `Runner.run_streamed` 执行，
  使用 `OpenAIChatCompletionsModel` 适配 DeepSeek，tracing 已关闭。

## SSE 事件

除原有的 `stream.open`、`response.status`、`response.delta`、
`response.completed`、`response.error` 外，还有：

- `tool.start`：`{type, name, arguments}`
- `tool.result`：`{type, name, result}`

`search_products` 的 `result` 包含 `count`、`products`（每项含 `price_yuan`、
`stock`、`category` 等），空结果时额外带 `hint`。

## 降级行为

mall 不可用时工具返回 `{"error": "商品服务暂时不可用。"}`，模型会说明
查不到实时价格与库存，聊天不中断、不返回 502。

## 测试

```powershell
uv run python -m unittest discover -s tests -v
```

## 接口

- `GET /health`：返回 `config_status`、`model`、`mall`、`prompt` 状态
- `POST /api/chat`，单轮非流式聊天（同样支持工具）
- `POST /api/chat/stream`，多轮 SSE 流式聊天