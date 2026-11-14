import { NextResponse } from "next/server";


type ChatRequest = {
  message?: unknown;
};

export async function POST(request: Request) {
  let body: ChatRequest;

  try {
    body = (await request.json()) as ChatRequest;
  } catch {
    return NextResponse.json({ detail: "请求格式无效。" }, { status: 400 });
  }

  if (typeof body.message !== "string" || !body.message.trim()) {
    return NextResponse.json({ detail: "请输入问题。" }, { status: 400 });
  }

  const agentUrl =
    process.env.AGENT_SERVICE_URL ?? "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${agentUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: body.message }),
      cache: "no-store",
      signal: AbortSignal.timeout(30000),
    });
    const data = (await response.json()) as {
      reply?: string;
      detail?: string;
    };

    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Agent 服务暂时不可用，请确认 8000 端口已启动。" },
      { status: 503 },
    );
  }
}
