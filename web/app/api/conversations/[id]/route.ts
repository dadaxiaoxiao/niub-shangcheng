import { MALL_API_URL } from "@/lib/mall";

export async function DELETE(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;

  try {
    const response = await fetch(
      `${MALL_API_URL}/api/conversations/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      },
    );

    if (response.status === 404) {
      return Response.json({ detail: "会话不存在。" }, { status: 404 });
    }
    if (!response.ok) {
      let detail = "删除会话失败。";
      try {
        const data = (await response.json()) as { detail?: string };
        detail = data.detail ?? detail;
      } catch {
        // Keep the generic message for non-JSON errors.
      }
      return Response.json({ detail }, { status: 502 });
    }
    return new Response(null, { status: 204 });
  } catch {
    return Response.json(
      { detail: "商城服务暂时不可用。" },
      { status: 503 },
    );
  }
}