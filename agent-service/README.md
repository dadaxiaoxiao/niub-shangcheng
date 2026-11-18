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
  demo_user_id: u-demo
```

- `mall.base_url` 指向 mall 的商品与个性化接口，默认 `http://127.0.0.1:3001`；
  mall 换端口时要同步修改。
- `mall.demo_user_id` 是演示用户 ID，默认 `u-demo`；画像、浏览、订单和购物车
  都按这个 ID 读取。
- `llm.max_turns` 控制 Agent SDK 的最大轮次，默认 6；超出时返回明确提示。

## 提示词

提示词正文在 `prompts/shopping_agent.md`，由 `llm.prompt_file` 指定：

- 相对路径以 agent-service 根目录为基准，绝对路径原样使用。
- 修改文件后下一个请求自动重新读取，不需要重启。
- 文件缺失、为空或不可读时，`/health` 的 `prompt` 为 `missing_or_invalid`，
  聊天接口返回 503。
- 旧配置里的 `llm.system_prompt` 会报迁移错误，需要把内容移到提示词文件。

## 商品推荐工具

模型通过 function calling 调用三个工具：

| 工具 | 作用 |
| --- | --- |
| `recommend_products` | 结合画像、浏览/搜索、订单、购物车，先取推荐系统候选，再取最多 1 个广告候选，并完成库存/价格/负反馈校验 |
| `search_products` | 按关键词、品类、最高价格和库存筛选商品，返回真实价格与库存 |
| `get_product` | 按商品 ID 获取详情 |

- 商品与个性化数据来自 mall 的内存 mock 接口；目录、画像、行为、订单和购物车
  在单次聊天请求内缓存，只读。
- `recommend_products` 的候选来自推荐服务，广告最多补 1 个并标记
  `sponsored: true`；购物车商品、已退货商品、命中画像 avoid 的商品、已购
  耐用品和超预算商品会被过滤。
- 提示词要求模型「先查后答」：只推荐工具返回的商品，不编造价格和库存；
  推荐场景固定输出 3 个，广告商品标注「（推广）」，候选不足时可用
  `search_products` 补充。
- 查询为空时工具结果会附带 `hint`，引导模型放宽关键词或改用具体品类。
- 工具参数用 Pydantic 校验，`search_products.limit` 限制在 1–10，
  `recommend_products.exclude_product_ids` 最多 20 个。
- ReAct 循环由 OpenAI Agents SDK 的 `Runner.run_streamed` 执行，
  使用 `OpenAIChatCompletionsModel` 适配 DeepSeek，tracing 已关闭。

## SSE 事件

除原有的 `stream.open`、`response.status`、`response.delta`、
`response.completed`、`response.error` 外，还有：

- `tool.start`：`{type, name, arguments}`
- `tool.result`：`{type, name, result}`

`search_products` 的 `result` 包含 `count`、`products`（每项含 `price_yuan`、
`stock`、`category` 等），空结果时额外带 `hint`。

`recommend_products` 的 `result` 包含：

- `profile`：画像摘要（会员等级、标签、偏好品类、价格带、avoid、场合）；
- `signals`：最近浏览、搜索、购物车、订单和复购到期；
- `candidates`：已校验的候选，每项含 `score`、`source`、`reason`、
  `sponsored`；
- `target_count`、`ad_slots_used`、`warnings`、`hint`。

## 降级行为

- mall 商品目录不可用时 `search_products` / `recommend_products` 返回
  `{"error": "商品服务暂时不可用。"}`，模型会说明查不到实时价格与库存，
  聊天不中断、不返回 502。
- 画像 404 视为冷启动；行为、订单、购物车、推荐或广告服务失败时，
  `recommend_products` 会写 `warnings` 并继续返回可用部分。
- 广告服务失败只跳过推广候选，不影响自然推荐。

## 测试

```powershell
uv run python -m unittest discover -s tests -v
```

## 接口

- `GET /health`：返回 `config_status`、`model`、`mall`、`prompt` 状态
- `POST /api/chat`，单轮非流式聊天（同样支持工具）
- `POST /api/chat/stream`，多轮 SSE 流式聊天