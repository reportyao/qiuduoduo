import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";

type InteractionEvent =
  | "focus_select"
  | "action_click"
  | "action_result"
  | "free_text_open"
  | "free_text_send"
  | "pulse_open"
  | "intel_expand"
  | "source_open"
  | "verdict_viewed"
  | "plan_viewed";

let sessionId = "";

function currentSessionId(): string {
  if (!sessionId) {
    sessionId = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }
  return sessionId;
}

/**
 * 最小漏斗埋点：只报事件/比赛/判决 ID，不带任何用户原始输入或 PII。
 * 失败静默，不能影响主流程。
 */
export function trackInteraction(
  event: InteractionEvent,
  payload: { matchId?: string; verdictId?: string; action?: string; metadata?: Record<string, unknown> } = {},
): void {
  const eventId = `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  void callApi(api.client.POST("/interactions", {
    body: {
      event,
      event_id: eventId,
      schema_ver: 1,
      session_id: currentSessionId(),
      match_id: payload.matchId ?? "",
      verdict_id: payload.verdictId ?? "",
      action: payload.action ?? "",
      metadata: payload.metadata ?? {},
    },
  })).catch(() => {});
}
