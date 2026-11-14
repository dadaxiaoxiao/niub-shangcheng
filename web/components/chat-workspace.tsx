"use client";

import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import styles from "@/app/chat/chat.module.css";


type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  meta?: string;
};

type StreamEvent = {
  type: "start" | "status" | "delta" | "done" | "error";
  messageId?: string;
  delta?: string;
  statusText?: string;
  timestamp?: string;
  elapsedMs?: number;
  sequence?: number;
  message?: string;
};

const WELCOME =
  "你好，我是牛脖商城的购物助手。你可以告诉我预算、使用场景或想送的人，我们慢慢把选择范围缩小。";

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

export default function ChatWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: WELCOME },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
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
    const requestMessages = [...messages, userMessage].map(
      ({ role, content: messageContent }) => ({
        role,
        content: messageContent,
      }),
    );

    setMessages((current) => [
      ...current,
      userMessage,
      assistantMessage,
    ]);
    setInput("");
    setIsStreaming(true);
    setStreamingId(assistantId);
    setStreamStatus("正在连接 SSE 服务");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: requestMessages }),
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

  function newConversation() {
    abortRef.current?.abort();
    setMessages([{ id: "welcome", role: "assistant", content: WELCOME }]);
    setInput("");
    setStreamStatus(null);
    textareaRef.current?.focus();
  }

  function useSuggestion(suggestion: string) {
    setInput(suggestion);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  return (
    <div className={styles.workspace}>
      <aside className={styles.sidebar}>
        <div>
          <a className={styles.backLink} href="/">
            <span aria-hidden="true">←</span>
            返回商城
          </a>

          <div className={styles.brand}>
            <span className={styles.brandMark}>牛</span>
            <div>
              <strong>牛脖商城</strong>
              <span>SHOPPING ASSISTANT</span>
            </div>
          </div>

          <div className={styles.intro}>
            <span className={styles.eyebrow}>A LITTLE HELP</span>
            <h1>一起挑件<br />真正合适的东西。</h1>
            <p>
              对话会保留在当前页面中，并由 Agent 服务实时调用模型。
              回复会随着模型生成逐段出现。
            </p>
          </div>
        </div>

        <div className={styles.sidebarFooter}>
          <span className={styles.pulseDot} />
          <div>
            <strong>真实模型 SSE</strong>
            <span>YAML 配置 · 流式响应</span>
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
            onClick={newConversation}
          >
            ＋ 新对话
          </button>
        </header>

        <div className={styles.thread} role="log" aria-live="polite">
          <div className={styles.threadIntro}>
            <span>今天想找点什么？</span>
            <p>可以直接描述预算、对象或使用场景。</p>
          </div>

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

          {messages.length === 1 && (
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
