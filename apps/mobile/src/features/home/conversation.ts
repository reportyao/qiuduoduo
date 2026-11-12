import AsyncStorage from "@react-native-async-storage/async-storage";
import type { ChatCard, SportmonksIntelData, VerdictSummary } from "@/domain/types";
import type { BriefMatchOption } from "@/features/home/components/BriefMatchPicker";

const STORAGE_PREFIX = "jieqiu.home.thread.v2";
const MAX_MESSAGES = 60;

export interface MatchIntelSummary {
  /** 缓存版本：名称本地化升级后，旧摘要不再展示。 */
  v?: number;
  homeFormation?: string;
  awayFormation?: string;
  injuries: string[];
  homePosition?: number | null;
  awayPosition?: number | null;
  homePoints?: number | null;
  awayPoints?: number | null;
  homeForm: string[];
  awayForm: string[];
  weather?: string;
  referee?: string;
  prediction?: string;
  market?: string;
  h2h?: string;
  news?: string;
  sections?: Record<string, string | null>;
  capturedAt?: string | null;
}

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
      intel?: MatchIntelSummary;
      at: number;
    }
  | {
      id: string;
      kind: "prediction";
      option: BriefMatchOption;
      verdict: VerdictSummary;
      lead: string;
      intel?: MatchIntelSummary;
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
  const probs = isObject(value.probs) ? value.probs : null;
  return typeof value.id === "string"
    && typeof value.matchId === "string"
    && typeof value.home === "string"
    && typeof value.away === "string"
    && probs !== null
    && typeof probs.home === "number"
    && typeof probs.draw === "number"
    && typeof probs.away === "number";
}

function pctText(value?: number | null): string {
  return value == null ? "—" : `${Math.round(value)}%`;
}

function predictionText(item: SportmonksIntelData["predictionHighlights"] extends
  (infer T)[] | undefined ? T : never): string {
  const values = item.values ?? {};
  if (item.key === "BTTS_PROBABILITY") return `是 ${pctText(values.yes)} / 否 ${pctText(values.no)}`;
  if (item.key === "OVER_UNDER_2_5_PROBABILITY") {
    return `大 ${pctText(values.yes)} / 小 ${pctText(values.no)}`;
  }
  if (item.key === "DOUBLE_CHANCE_PROBABILITY") {
    return `主/平 ${pctText(values.draw_home)} / 平/客 ${pctText(values.draw_away)}`;
  }
  if (item.key === "FIRST_HALF_WINNER_PROBABILITY") {
    return `主 ${pctText(values.home)} / 平 ${pctText(values.draw)} / 客 ${pctText(values.away)}`;
  }
  if (item.key === "TEAM_TO_SCORE_FIRST_PROBABILITY") {
    return `主先进 ${pctText(values.home)} / 客先进 ${pctText(values.away)}`;
  }
  if (values.home != null || values.draw != null || values.away != null) {
    return `主 ${pctText(values.home)} / 平 ${pctText(values.draw)} / 客 ${pctText(values.away)}`;
  }
  const first = Object.values(values).find((value) => value != null);
  return first != null ? pctText(first) : item.label;
}

function topPrediction(data: SportmonksIntelData): string | undefined {
  const highlights = data.predictionHighlights ?? [];
  const preferred = ["MATCH_WINNER_PROBABILITY", "FULLTIME_RESULT_PROBABILITY",
    "BTTS_PROBABILITY", "OVER_UNDER_2_5_PROBABILITY", "DOUBLE_CHANCE_PROBABILITY"];
  for (const key of preferred) {
    const item = highlights.find((entry) => entry.key === key);
    if (item) return `${item.label} ${predictionText(item)}`;
  }
  const item = highlights.find((entry) => Object.keys(entry.values ?? {}).length > 0);
  return item ? `${item.label} ${predictionText(item)}` : undefined;
}

export function summarizeIntel(
  data: SportmonksIntelData | null | undefined,
): MatchIntelSummary | undefined {
  if (!data) return undefined;
  const home = data.standings?.home;
  const away = data.standings?.away;
  const market = data.marketBoard?.[0];
  const marketPick = market?.selections?.[0];
  const lastH2h = data.h2h?.[0];
  const sections: Record<string, string | null> = {};
  for (const [key, meta] of Object.entries(data.sections ?? {})) {
    sections[key] = meta.capturedAt ?? null;
  }
  return {
    v: 2,
    homeFormation: data.formations?.home || data.lineups?.home?.formation,
    awayFormation: data.formations?.away || data.lineups?.away?.formation,
    injuries: (data.sidelined ?? []).map((row) => row.playerName).filter(Boolean).slice(0, 4),
    homePosition: home?.position,
    awayPosition: away?.position,
    homePoints: home?.points,
    awayPoints: away?.points,
    homeForm: home?.form ?? data.recent?.home ?? [],
    awayForm: away?.form ?? data.recent?.away ?? [],
    weather: data.weather?.description,
    referee: data.referees?.main?.name,
    prediction: topPrediction(data),
    market: marketPick
      ? `${marketPick.label} ${pctText(marketPick.probability)}`
      : undefined,
    h2h: lastH2h
      ? `${data.h2h?.length ?? 0} 场 · 最近 ${lastH2h.scoreHome}-${lastH2h.scoreAway}`
      : undefined,
    news: data.prematchNews?.[0]?.title,
    sections,
    capturedAt: data.capturedAt ?? null,
  };
}

function isSummary(value: unknown): value is MatchIntelSummary {
  return isObject(value) && value.v === 2 && Array.isArray(value.injuries);
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
        intel: isSummary(entry.intel) ? entry.intel : undefined,
        at,
      });
    } else if (entry.kind === "prediction" && isOption(entry.option)
        && isVerdict(entry.verdict)) {
      messages.push({
        id: entry.id,
        kind: "prediction",
        option: entry.option,
        verdict: entry.verdict,
        lead: typeof entry.lead === "string" ? entry.lead : "这场的完整预测在这里。",
        intel: isSummary(entry.intel) ? entry.intel : undefined,
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

export function updateHomeMatchIntel(
  messages: HomeConversationMessage[],
  matchId: string,
  intel: MatchIntelSummary,
): HomeConversationMessage[] {
  let changed = false;
  const next = messages.map((message) => {
    if ((message.kind !== "match" && message.kind !== "prediction")
        || message.option.matchId !== matchId) return message;
    if (JSON.stringify(message.intel) === JSON.stringify(intel)) return message;
    changed = true;
    return { ...message, intel };
  });
  return changed ? next : messages;
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
