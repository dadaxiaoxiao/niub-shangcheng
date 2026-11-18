# Agent 协作说明

## 计划 / 规格文档

- 每个功能的计划、设计决策和验收标准写入 `spec/<feature>.md`，实现前先确认。
- 实现过程中方案有变化时，同步更新对应 spec 文件。
- 新功能先看 `spec/` 里是否已有相关规格，避免重复设计。

## 启动 / 运行本项目

**先读 [reader.md](reader.md)，不要从零摸索。** 完整教程见 [README.md](README.md)。

- 本机端口固定为：mall **3011**（3001 被系统进程占用）、agent-service 8000、web 3000。
- 启动前先探活，已健康就直接给用户访问地址，**不要重复启动**：

  ```bash
  curl -s http://127.0.0.1:3011/health
  curl -s http://127.0.0.1:8000/health
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
  ```

- 需要启动时按 mall → agent-service → web 的顺序，命令见 `reader.md`。
- 改端口必须同步 `web/.env.local` 的 `MALL_API_URL` 与
  `agent-service/config/llm.yaml` 的 `mall.base_url`。