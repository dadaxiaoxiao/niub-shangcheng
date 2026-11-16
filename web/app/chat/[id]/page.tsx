import type { Metadata } from "next";
import { notFound } from "next/navigation";

import ChatWorkspace from "@/components/chat-workspace";
import { fetchConversation, fetchConversations } from "@/lib/mall";


export const metadata: Metadata = {
  title: "历史对话 | 牛逼商城",
  description: "查看与牛逼商城购物助手的历史对话。",
};

export const dynamic = "force-dynamic";

export default async function ChatConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [history, lookup] = await Promise.all([
    fetchConversations(),
    fetchConversation(id),
  ]);

  if (lookup.status === "not_found") {
    notFound();
  }

  if (lookup.status === "database_unavailable") {
    return (
      <main className="service-page">
        <div className="service-notice">
          <strong>数据库尚未初始化</strong>
          <p>{lookup.detail ?? "会话历史需要 MySQL 数据库。"}</p>
          <p>
            在 <code>mall</code> 目录执行{" "}
            <code>uv run python -m mall.init_db</code>，或用 MySQL 客户端执行{" "}
            <code>mall/schema.sql</code>，然后刷新页面。
          </p>
        </div>
      </main>
    );
  }

  if (lookup.status === "unavailable") {
    return (
      <main className="service-page">
        <div className="service-notice">
          <strong>历史对话暂时无法加载</strong>
          <p>请确认商城 HTTP 服务已启动，然后刷新页面。</p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <ChatWorkspace
        conversations={history.items}
        initialConversation={lookup.conversation}
        historyState={history.state}
      />
    </main>
  );
}