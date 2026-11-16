import { MALL_API_URL } from "@/lib/mall";

type StreamRequest = {
  conversationId?: unknown;
  message?: unknown;
};

type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type StreamEvent = {
  type?: string;
  delta?: string;
  message?: string;
  conversationId?: string;
};

const AGENT_URL = process.env.AGENT_SERVICE_URL ?? "http://127.0.0.1:8000";
const HISTORY_LIMIT = 49;
const MESSAGE_LIMIT = 4000;

export const dynamic = "force-dynamic";

function parseEvent(block: string): StreamEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");

  if (!data) {
    return null;
  }

  try {
    return JSON.parse(data) as StreamEvent;
  } catch {
    return null;
  }
}

function sseFrame(name: string, data: Record<string, unknown>): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

function mallFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${MALL_API_URL}${path}`, { cache: "no-store", ...init });
}

function mallError(detail: string, status: number): Response {
  return Response.json({ detail }, { status });
}

async function responseDetail(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail) {
      return data.detail;
    }
  } catch {
    // Ignore non-JSON error responses.
  }
  return fallback;
}

export async function POST(request: Request) {
  let body: StreamRequest;

  try {
    body = (await request.json()) as StreamRequest;
  } catch {
    return mallError("请求格式无效。", 400);
  }

  const message =
    typeof body.message === "string" ? body.message.trim() : "";
  if (!message) {
    return mallError("请输入问题。", 400);
  }
  if (message.length > MESSAGE_LIMIT) {
    return mallError("消息过长。", 400);
  }

  let conversationId =
    typeof body.conversationId === "string" && body.conversationId
      ? body.conversationId
      : null;
  let createdConversation = false;
  let serviceDetail: string | null = null;

  try {
    if (conversationId) {
      const existing = await mallFetch(
        `/api/conversations/${encodeURIComponent(conversationId)}`,
      );
      if (existing.status === 404) {
        return mallError("会话不存在。", 404);
      }
      if (!existing.ok) {
        return mallError(
          await responseDetail(existing, "历史服务暂时不可用。"),
          503,
        );
      }
    } else {
      const created = await mallFetch("/api/conversations", { method: "POST" });
      if (!created.ok) {
        return mallError(
          await responseDetail(created, "无法创建会话。"),
          503,
        );
      }
      const data = (await created.json()) as { id: string };
      conversationId = data.id;
      createdConversation = true;
    }

    const appended = await mallFetch(
      `/api/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "user", content: message }),
      },
    );
    if (!appended.ok) {
      serviceDetail = await responseDetail(appended, "无法保存消息。");
      throw new Error(serviceDetail);
    }

    const historyResponse = await mallFetch(
      `/api/conversations/${conversationId}/messages?limit=${HISTORY_LIMIT}`,
    );
    if (!historyResponse.ok) {
      serviceDetail = await responseDetail(
        historyResponse,
        "无法读取会话历史。",
      );
      throw new Error(serviceDetail);
    }
    const history = (await historyResponse.json()) as HistoryMessage[];

    let upstream: Response;
    try {
      upstream = await fetch(`${AGENT_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.map(({ role, content }) => ({
            role,
            content: content.slice(0, MESSAGE_LIMIT),
          })),
        }),
        cache: "no-store",
        signal: request.signal,
      });
    } catch {
      return mallError("Agent 服务不可用，请确认 8000 端口已启动。", 503);
    }

    if (!upstream.ok || !upstream.body) {
      let detail = "Agent 服务返回错误。";
      try {
        const data = (await upstream.json()) as { detail?: string };
        detail = data.detail ?? detail;
      } catch {
        // Keep the generic message for non-JSON upstream errors.
      }
      return mallError(detail, upstream.status || 502);
    }

    const reader = upstream.body.getReader();
    const decoder = new TextDecoder();
    const encoder = new TextEncoder();
    const activeConversationId = conversationId;

    let assistantText = "";
    let completed = false;
    let streamOpen = true;

    async function persistAssistant(status: "complete" | "interrupted") {
      if (!assistantText.trim()) {
        return;
      }
      try {
        await mallFetch(
          `/api/conversations/${activeConversationId}/messages`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              role: "assistant",
              content: assistantText,
              status,
            }),
          },
        );
      } catch {
        // Best effort: a failed save must not break the response stream.
      }
    }

    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        const push = (chunk: string | Uint8Array) => {
          if (!streamOpen) {
            return;
          }
          try {
            controller.enqueue(
              typeof chunk === "string" ? encoder.encode(chunk) : chunk,
            );
          } catch {
            streamOpen = false;
          }
        };

        push(
          sseFrame("conversation", {
            type: "conversation",
            conversationId: activeConversationId,
            timestamp: new Date().toISOString(),
          }),
        );

        let buffer = "";
        try {
          while (true) {
            const { value, done } = await reader.read();
            if (done) {
              break;
            }
            if (!value) {
              continue;
            }
            push(value);
            buffer += decoder.decode(value, { stream: true });
            buffer = buffer.replace(/\r\n/g, "\n");

            const blocks = buffer.split("\n\n");
            buffer = blocks.pop() ?? "";

            for (const block of blocks) {
              const event = parseEvent(block);
              if (event?.type === "delta" && typeof event.delta === "string") {
                assistantText += event.delta;
              }
              if (event?.type === "done") {
                completed = true;
              }
            }
          }
        } catch {
          push(
            sseFrame("response.error", {
              type: "error",
              message: "流式连接中断。",
            }),
          );
        } finally {
          await persistAssistant(completed ? "complete" : "interrupted");
          if (streamOpen) {
            try {
              controller.close();
            } catch {
              streamOpen = false;
            }
          }
        }
      },
      cancel() {
        streamOpen = false;
        void reader.cancel();
      },
    });

    return new Response(stream, {
      status: upstream.status,
      headers: {
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "Content-Type":
          upstream.headers.get("Content-Type") ??
          "text/event-stream; charset=utf-8",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    if (createdConversation && conversationId) {
      try {
        await mallFetch(
          `/api/conversations/${encodeURIComponent(conversationId)}`,
          { method: "DELETE" },
        );
      } catch {
        // Ignore cleanup failures.
      }
    }
    return mallError(
      serviceDetail ?? "会话服务暂时不可用，请确认商城服务已启动。",
      503,
    );
  }
}