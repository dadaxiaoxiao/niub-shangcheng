"use client";

import { FormEvent, useState } from "react";


type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type ChatResponse = {
  reply?: string;
  detail?: string;
};

const WELCOME =
  "你好，我是牛脖商城的购物助手。告诉我预算或使用场景，我来帮你一起挑。";

export default function AgentChat() {
  const [messages, setMessages] = useState<Message[]>([
    { id: "welcome", role: "assistant", content: WELCOME },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isLoading) {
      return;
    }

    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: message },
    ]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = (await response.json()) as ChatResponse;

      if (!response.ok) {
        throw new Error(data.detail ?? "购物助手暂时无法回答。");
      }

      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.reply || "我没有得到有效回复，请稍后再试。",
        },
      ]);
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : "购物助手暂时无法回答。";
      setMessages((current) => [
        ...current,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: `连接服务时遇到问题：${detail}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-heading">
        <div>
          <span className="status-dot" />
          <strong>购物助手</strong>
        </div>
        <span>由 AI 提供服务</span>
      </div>

      <div className="message-list" aria-live="polite">
        {messages.map((message) => (
          <div className={`message ${message.role}`} key={message.id}>
            {message.content}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant loading">正在认真想...</div>
        )}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="chat-message">
          你的问题
        </label>
        <textarea
          id="chat-message"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="例如：三百元以内，适合送朋友的礼物？"
          maxLength={4000}
          rows={2}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>
          {isLoading ? "思考中" : "发送"}
        </button>
      </form>
    </div>
  );
}

