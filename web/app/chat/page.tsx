import type { Metadata } from "next";

import ChatWorkspace from "@/components/chat-workspace";


export const metadata: Metadata = {
  title: "购物助手 | 牛脖商城",
  description: "与牛脖商城购物助手进行多轮对话。",
};

export default function ChatPage() {
  return (
    <main>
      <ChatWorkspace />
    </main>
  );
}

