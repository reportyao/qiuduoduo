import AsyncStorage from "@react-native-async-storage/async-storage";
import type { ChatCard, VerdictSummary } from "@/domain/types";
import type { BriefMatchOption } from "@/features/home/components/BriefMatchPicker";

const STORAGE_PREFIX = "jieqiu.home.thread.v2";
const MAX_MESSAGES = 60;

export type HomeConversationMessage =
  | {
      id: string;
      kind: "user";
      text: string;
      at: number;
    }
  | {
      id: string;
      kind: "assistant";
      text: string;
      card?: ChatCard;
      error?: boolean;
      confirmed?: boolean;
      at: number;
    }
  | {
      id: string;
      kind: "match";
      option: BriefMatchOption;
      verdict: VerdictSummary | null;
      at: number;
    };

export function homeThreadKey(userId: string, date: string): string {
  return `${STORAGE_PREFIX}.${userId || "local"}.${date}`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isOption(value: unknown): value is BriefMatchOption {
  if (!isObject(value)) return false;
  return typeof value.matchId === "string"
    && typeof value.home === "string"
    && typeof value.away === "string"
    && typeof value.kickoff === "string";
}

function isVerdict(value: unknown): value is VerdictSummary {
  if (!isObject(value)) return false;
  return typeof value.id === "string"
    && typeof value.matchId === "string"
    && typeof value.home === "string"
    && typeof value.away === "string";
}

export function parseHomeMessages(raw: string | null): HomeConversationMessage[] {
  if (!raw) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];
  const messages: HomeConversationMessage[] = [];
  for (const entry of parsed) {
    if (!isObject(entry) || typeof entry.id !== "string") continue;
    const at = typeof entry.at === "number" ? entry.at : 0;
    if (entry.kind === "user" && typeof entry.text === "string") {
      messages.push({ id: entry.id, kind: "user", text: entry.text, at });
    } else if (entry.kind === "assistant" && typeof entry.text === "string") {
      messages.push({
        id: entry.id,
        kind: "assistant",
        text: entry.text,
        card: isObject(entry.card)
          && typeof entry.card.type === "string"
          && typeof entry.card.text === "string"
          ? entry.card as unknown as ChatCard
          : undefined,
        error: Boolean(entry.error),
        confirmed: Boolean(entry.confirmed),
        at,
      });
    } else if (entry.kind === "match" && isOption(entry.option)) {
      messages.push({
        id: entry.id,
        kind: "match",
        option: entry.option,
        verdict: isVerdict(entry.verdict) ? entry.verdict : null,
        at,
      });
    }
  }
  return messages.slice(-MAX_MESSAGES);
}

export function appendHomeMessage(
  messages: HomeConversationMessage[],
  message: HomeConversationMessage,
): HomeConversationMessage[] {
  return [...messages, message].slice(-MAX_MESSAGES);
}

export function markHomeMessageConfirmed(
  messages: HomeConversationMessage[],
  messageId: string,
): HomeConversationMessage[] {
  return messages.map((message) =>
    message.id === messageId && message.kind === "assistant"
      ? { ...message, confirmed: true }
      : message);
}

export async function loadHomeMessages(key: string): Promise<HomeConversationMessage[]> {
  try {
    return parseHomeMessages(await AsyncStorage.getItem(key));
  } catch {
    return [];
  }
}

export async function saveHomeMessages(
  key: string,
  messages: HomeConversationMessage[],
): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(messages.slice(-MAX_MESSAGES)));
  } catch {
    // 本地历史写失败不能阻塞对话；本次会话仍保留内存中的消息。
  }
}
