"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  ConversationDetail,
  ConversationSummary,
  HistoryState,
} from "@/lib/mall";
import styles from "@/app/chat/chat.module.css";


type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  meta?: string;
};

type StreamEvent = {
  type: "start" | "status" | "delta" | "done" | "error" | "conversation";
  messageId?: string;
  delta?: string;
  statusText?: string;
  timestamp?: string;
  elapsedMs?: number;
  sequence?: number;
  message?: string;
  conversationId?: string;
};

type ChatWorkspaceProps = {
  conversations: ConversationSummary[];
  initialConversation?: ConversationDetail;
  historyState: HistoryState;
};

const WELCOME =
  "你好，我是牛逼商城的购物助手。你可以告诉我预算、使用场景或想送的人，我们慢慢把选择范围缩小。";

const SUGGESTIONS = [
  "300 元以内，适合送朋友什么？",
  "帮我挑一件适合办公室的茶具",
  "想要让房间安静下来的香氛",
];

function createId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function formatClock(timestamp?: string): string {
  if (!timestamp) {
    return "--:--:--";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

function formatMessageTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const sameDay = date.toDateString() === new Date().toDateString();
  return new Intl.DateTimeFormat(
    "zh-CN",
    sameDay
      ? { hour: "2-digit", minute: "2-digit", hour12: false }
      : {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        },
  ).format(date);
}

function formatRelative(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const diff = Date.now() - date.getTime();
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) {
    return "刚刚";
  }
  if (diff < hour) {
    return `${Math.floor(diff / minute)} 分钟前`;
  }
  if (diff < day) {
    return `${Math.floor(diff / hour)} 小时前`;
  }
  if (diff < 7 * day) {
    return `${Math.floor(diff / day)} 天前`;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function readSseBlock(block: string): StreamEvent | null {
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

function buildInitialMessages(
  conversation?: ConversationDetail,
): ChatMessage[] {
  if (!conversation || conversation.messages.length === 0) {
    return [{ id: "welcome", role: "assistant", content: WELCOME }];
  }
  return conversation.messages.map((message) => ({
    id: `message-${message.id}`,
    role: message.role,
    content: message.content,
    meta: formatMessageTime(message.created_at),
  }));
}

export default function ChatWorkspace({
  conversations,
  initialConversation,
  historyState,
}: ChatWorkspaceProps) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    buildInitialMessages(initialConversation),
  );
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversation?.id ?? null,
  );
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: isStreaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, isStreaming]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 152)}px`;
  }, [input]);

  async function sendMessage(text: string) {
    const content = text.trim();
    if (!content || isStreaming) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createId("user"),
      role: "user",
      content,
      meta: formatClock(new Date().toISOString()),
    };
    const assistantId = createId("assistant");
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setIsStreaming(true);
    setStreamingId(assistantId);
    setStreamStatus("正在连接 SSE 服务");
    setHistoryError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversationId, message: content }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = (await response.json()) as { detail?: string };
        throw new Error(error.detail ?? "流式服务暂时不可用。");
      }
      if (!response.body) {
        throw new Error("浏览器没有收到流式响应。");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventCount = 0;
      let firstEventTimestamp: string | undefined;
      let lastEventTimestamp: string | undefined;

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        buffer = buffer.replace(/\r\n/g, "\n");

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const streamEvent = readSseBlock(block);
          if (streamEvent) {
            eventCount += 1;
            firstEventTimestamp ??= streamEvent.timestamp;
            lastEventTimestamp = streamEvent.timestamp ?? lastEventTimestamp;
          }
          if (
            streamEvent?.type === "conversation" &&
            streamEvent.conversationId
          ) {
            setConversationId(streamEvent.conversationId);
            window.history.replaceState(
              null,
              "",
              `/chat/${streamEvent.conversationId}`,
            );
          }
          if (streamEvent?.type === "status" && streamEvent.statusText) {
            setStreamStatus(streamEvent.statusText);
          }
          if (streamEvent?.type === "delta" && streamEvent.delta) {
            setStreamStatus(null);
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: message.content + streamEvent.delta,
                    }
                  : message,
              ),
            );
          }
          if (streamEvent?.type === "error") {
            throw new Error(streamEvent.message ?? "流式回复中断。");
          }
        }

        if (done) {
          break;
        }
      }

      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                meta: `${formatClock(firstEventTimestamp)} → ${formatClock(
                  lastEventTimestamp,
                )} · ${eventCount} 个 SSE 事件`,
              }
            : message,
        ),
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId && !message.content
              ? { ...message, content: "已停止生成。" }
              : message,
          ),
        );
      } else {
        const detail =
          error instanceof Error ? error.message : "流式回复失败。";
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content: message.content
                    ? `${message.content}\n\n[连接中断：${detail}]`
                    : `连接中断：${detail}`,
                }
              : message,
          ),
        );
      }
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
      setStreamingId(null);
      setStreamStatus(null);
      textareaRef.current?.focus();
      router.refresh();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      if (!isStreaming && input.trim()) {
        void sendMessage(input);
      }
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  function startNewConversation() {
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([{ id: "welcome", role: "assistant", content: WELCOME }]);
    setInput("");
    setStreamStatus(null);
    setHistoryError(null);
    router.push("/chat");
    textareaRef.current?.focus();
  }

  async function removeConversation(id: string) {
    if (!window.confirm("删除这个会话？对话内容将无法恢复。")) {
      return;
    }

    setHistoryError(null);
    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      );
      if (!response.ok && response.status !== 404) {
        throw new Error("删除失败，请稍后再试。");
      }

      if (id === conversationId) {
        abortRef.current?.abort();
        setConversationId(null);
        setMessages([{ id: "welcome", role: "assistant", content: WELCOME }]);
        setInput("");
        router.push("/chat");
      } else {
        router.refresh();
      }
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "删除失败。");
    }
  }

  function useSuggestion(suggestion: string) {
    setInput(suggestion);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  const showEmptyState = !conversationId && messages.length === 1;

  return (
    <div className={styles.workspace}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTop}>
          <div className={styles.sidebarHeading}>
            <a className={styles.backLink} href="/">
              <span aria-hidden="true">←</span>
              返回商城
            </a>

            <div className={styles.brand}>
              <span className={styles.brandMark}>牛</span>
              <div>
                <strong>牛逼商城</strong>
                <span>SHOPPING ASSISTANT</span>
              </div>
            </div>
          </div>

          <section className={styles.history} aria-label="历史会话">
            <div className={styles.historyHeading}>
              <span>历史会话</span>
              <span>{conversations.length}</span>
            </div>

            {historyState === "database_unavailable" && (
              <p className={styles.historyNotice}>
                数据库尚未初始化。请在 mall 目录执行：
                <code>uv run python -m mall.init_db</code>
                然后刷新页面。
              </p>
            )}
            {historyState === "unavailable" && (
              <p className={styles.historyNotice}>历史记录暂时不可用。</p>
            )}
            {historyState === "ok" && conversations.length === 0 && (
              <p className={styles.historyNotice}>还没有保存的对话。</p>
            )}

            <ul className={styles.historyList}>
              {conversations.map((conversation) => (
                <li
                  key={conversation.id}
                  className={`${styles.historyItem} ${
                    conversation.id === conversationId
                      ? styles.historyItemActive
                      : ""
                  }`}
                >
                  <Link
                    className={styles.historyLink}
                    href={`/chat/${conversation.id}`}
                    onClick={() => abortRef.current?.abort()}
                  >
                    <span className={styles.historyTitle}>
                      {conversation.title || "新对话"}
                    </span>
                    <span className={styles.historyMeta}>
                      <span>{formatRelative(conversation.updated_at)}</span>
                      <span>{conversation.message_count} 条</span>
                    </span>
                    <span className={styles.historyPreview}>
                      {conversation.preview || "暂无消息"}
                    </span>
                  </Link>
                  <button
                    className={styles.historyDelete}
                    type="button"
                    aria-label={`删除会话：${conversation.title || "新对话"}`}
                    onClick={() => void removeConversation(conversation.id)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>

            {historyError && (
              <p className={styles.historyNotice}>{historyError}</p>
            )}
          </section>
        </div>

        <div className={styles.sidebarFooter}>
          <span className={styles.pulseDot} />
          <div>
            <strong>真实模型 SSE</strong>
            <span>流式响应 · MySQL 历史</span>
          </div>
        </div>
      </aside>

      <section className={styles.conversation}>
        <header className={styles.header}>
          <div className={styles.headerIdentity}>
            <span className={styles.avatar}>助</span>
            <div>
              <h2>购物助手</h2>
              <p>
                <span className={styles.onlineDot} />
                在线 · 模型对话
              </p>
            </div>
          </div>
          <button
            className={styles.newChatButton}
            type="button"
            onClick={startNewConversation}
          >
            ＋ 新对话
          </button>
        </header>

        <div className={styles.thread} role="log" aria-live="polite">
          {showEmptyState && (
            <div className={styles.threadIntro}>
              <span>今天想找点什么？</span>
              <p>可以直接描述预算、对象或使用场景。</p>
            </div>
          )}

          {messages.map((message) => (
            <article
              className={`${styles.messageRow} ${styles[message.role]}`}
              key={message.id}
            >
              {message.role === "assistant" && (
                <span className={styles.messageAvatar}>助</span>
              )}
              <div className={styles.messageBody}>
                <span className={styles.messageLabel}>
                  {message.role === "assistant" ? "购物助手" : "你"}
                </span>
                <div className={styles.bubble}>
                  {message.content || (
                    <span className={styles.thinking}>
                      <i />
                      <i />
                      <i />
                    </span>
                  )}
                  {message.id === streamingId && message.content && (
                    <span className={styles.cursor} aria-hidden="true" />
                  )}
                </div>
                {message.id === streamingId && streamStatus && (
                  <span className={styles.streamStatus}>{streamStatus}</span>
                )}
                {message.meta && (
                  <span className={styles.messageMeta}>{message.meta}</span>
                )}
              </div>
            </article>
          ))}

          {showEmptyState && (
            <div className={styles.suggestions}>
              {SUGGESTIONS.map((suggestion, index) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => useSuggestion(suggestion)}
                >
                  <span>0{index + 1}</span>
                  {suggestion}
                  <i aria-hidden="true">↗</i>
                </button>
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className={styles.composerArea}>
          <form className={styles.composer} onSubmit={handleSubmit}>
            <label className={styles.srOnly} htmlFor="chat-page-input">
              输入消息
            </label>
            <textarea
              id="chat-page-input"
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="说说你的预算、使用场景或想送的人..."
              rows={1}
              maxLength={4000}
              disabled={isStreaming}
            />
            {isStreaming ? (
              <button
                className={styles.stopButton}
                type="button"
                onClick={stopStreaming}
                aria-label="停止生成"
              >
                <span />
              </button>
            ) : (
              <button
                className={styles.sendButton}
                type="submit"
                disabled={!input.trim()}
                aria-label="发送消息"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 12h13M13 6l6 6-6 6" />
                </svg>
              </button>
            )}
          </form>
          <p>Enter 发送 · Shift + Enter 换行</p>
        </div>
      </section>
    </div>
  );
}