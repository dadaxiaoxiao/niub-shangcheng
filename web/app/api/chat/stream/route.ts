type ChatRole = "user" | "assistant";

type ChatMessage = {
  role: ChatRole;
  content: string;
};

type ChatRequest = {
  messages?: unknown;
};

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") {
    return false;
  }

  const message = value as Partial<ChatMessage>;
  return (
    (message.role === "user" || message.role === "assistant") &&
    typeof message.content === "string" &&
    message.content.trim().length > 0 &&
    message.content.length <= 4000
  );
}

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: ChatRequest;

  try {
    body = (await request.json()) as ChatRequest;
  } catch {
    return Response.json({ detail: "请求格式无效。" }, { status: 400 });
  }

  if (
    !Array.isArray(body.messages) ||
    body.messages.length === 0 ||
    body.messages.length > 50 ||
    !body.messages.every(isChatMessage) ||
    !body.messages.some((message) => message.role === "user")
  ) {
    return Response.json({ detail: "对话消息格式无效。" }, { status: 400 });
  }

  const agentUrl =
    process.env.AGENT_SERVICE_URL ?? "http://127.0.0.1:8000";

  let upstream: Response;
  try {
    upstream = await fetch(`${agentUrl}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: body.messages }),
      cache: "no-store",
      signal: request.signal,
    });
  } catch {
    return Response.json(
      { detail: "Agent 服务不可用，请确认 8000 端口已启动。" },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    let detail = "Agent 服务返回错误。";
    try {
      const data = (await upstream.json()) as { detail?: string };
      detail = data.detail ?? detail;
    } catch {
      // Keep the generic message for non-JSON upstream errors.
    }
    return Response.json(
      { detail },
      { status: upstream.status || 502 },
    );
  }

  return new Response(upstream.body, {
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
}
