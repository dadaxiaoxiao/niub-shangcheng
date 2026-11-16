export type ConversationSummary = {
  id: string;
  title: string;
  preview: string;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  status: "complete" | "interrupted";
  created_at: string;
};

export type ConversationDetail = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
};

export const MALL_API_URL =
  process.env.MALL_API_URL ?? "http://127.0.0.1:3001";

const TIMEOUT_MS = 3000;

export type HistoryState = "ok" | "unavailable" | "database_unavailable";

export async function fetchConversations(): Promise<{
  state: HistoryState;
  items: ConversationSummary[];
}> {
  try {
    const response = await fetch(`${MALL_API_URL}/api/conversations`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (response.status === 503) {
      return { state: "database_unavailable", items: [] };
    }
    if (!response.ok) {
      return { state: "unavailable", items: [] };
    }
    return {
      state: "ok",
      items: (await response.json()) as ConversationSummary[],
    };
  } catch {
    return { state: "unavailable", items: [] };
  }
}

export type ConversationLookup =
  | { status: "ok"; conversation: ConversationDetail }
  | { status: "not_found" }
  | { status: "database_unavailable"; detail?: string }
  | { status: "unavailable" };

export async function fetchConversation(
  id: string,
): Promise<ConversationLookup> {
  try {
    const response = await fetch(
      `${MALL_API_URL}/api/conversations/${encodeURIComponent(id)}`,
      { cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS) },
    );
    if (response.status === 404) {
      return { status: "not_found" };
    }
    if (response.status === 503) {
      let detail: string | undefined;
      try {
        const data = (await response.json()) as { detail?: string };
        detail = data.detail;
      } catch {
        detail = undefined;
      }
      return { status: "database_unavailable", detail };
    }
    if (!response.ok) {
      return { status: "unavailable" };
    }
    return {
      status: "ok",
      conversation: (await response.json()) as ConversationDetail,
    };
  } catch {
    return { status: "unavailable" };
  }
}