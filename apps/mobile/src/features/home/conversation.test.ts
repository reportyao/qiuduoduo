import { describe, expect, it } from "vitest";
import {
  appendHomeMessage,
  homeThreadKey,
  markHomeMessageConfirmed,
  parseHomeMessages,
  type HomeConversationMessage,
} from "./conversation";

const match: HomeConversationMessage = {
  id: "m-1",
  kind: "match",
  at: 1,
  option: {
    matchId: "match-1",
    verdictId: "verdict-1",
    matchNo: "周四001",
    league: "欧国联",
    home: "德国",
    away: "法国",
    kickoff: "2026-11-13 03:45:00",
    tier: "market_reference",
  },
  verdict: null,
};

describe("home conversation persistence", () => {
  it("keys threads by user and trade date", () => {
    expect(homeThreadKey("u1", "2026-11-12")).toContain("u1");
    expect(homeThreadKey("u1", "2026-11-12")).toContain("2026-11-12");
    expect(homeThreadKey("u1", "2026-11-12")).not.toBe(homeThreadKey("u2", "2026-11-12"));
  });

  it("round-trips a match card and chat answer", () => {
    const messages = appendHomeMessage(appendHomeMessage([], match), {
      id: "a-1",
      kind: "assistant",
      text: "这场是市场参考。",
      at: 2,
      card: { type: "match_analysis", text: "这场是市场参考。" },
    });
    const parsed = parseHomeMessages(JSON.stringify(messages));
    expect(parsed).toHaveLength(2);
    expect(parsed[0]).toMatchObject({ kind: "match", option: { matchId: "match-1" } });
    expect(parsed[1]).toMatchObject({ kind: "assistant", card: { type: "match_analysis" } });
  });

  it("drops malformed rows instead of crashing the thread", () => {
    const parsed = parseHomeMessages(JSON.stringify([
      { id: "ok", kind: "user", text: "你好", at: 1 },
      { id: "bad", kind: "match", option: { home: "德国" } },
      { kind: "user", text: "没有 id" },
      "not-an-object",
    ]));
    expect(parsed).toEqual([{ id: "ok", kind: "user", text: "你好", at: 1 }]);
  });

  it("marks memory conflicts as confirmed", () => {
    const messages: HomeConversationMessage[] = [
      { id: "a-1", kind: "assistant", text: "冲突", at: 1, card: { type: "memory_write", text: "冲突" } },
      match,
    ];
    const confirmed = markHomeMessageConfirmed(messages, "a-1");
    expect(confirmed[0]).toMatchObject({ confirmed: true });
    expect(confirmed[1]).toBe(match);
  });
});
