import type { Metadata } from "next";

import ChatWorkspace from "@/components/chat-workspace";
import { fetchConversations } from "@/lib/mall";


export const metadata: Metadata = {
  title: "购物助手 | 牛逼商城",
  description: "与牛逼商城购物助手进行多轮对话。",
};

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  const history = await fetchConversations();

  return (
    <main>
      <ChatWorkspace
        conversations={history.items}
        historyState={history.state}
      />
    </main>
  );
}