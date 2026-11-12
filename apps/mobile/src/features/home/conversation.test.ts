import { describe, expect, it } from "vitest";
import {
  appendHomeMessage,
  homeThreadKey,
  markHomeMessageConfirmed,
  parseHomeMessages,
  summarizeIntel,
  updateHomeMatchIntel,
  type HomeConversationMessage,
} from "./conversation";
import type { SportmonksIntelData } from "@/domain/types";

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
      text: "这场是预测。",
      at: 2,
      card: { type: "match_analysis", text: "这场是预测。" },
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

  it("round-trips an assistant prediction card", () => {
    const prediction: HomeConversationMessage = {
      id: "p-1",
      kind: "prediction",
      at: 3,
      option: match.option,
      verdict: {
        id: "verdict-1",
        matchId: "match-1",
        matchNo: "周四001",
        league: "欧国联",
        home: "德国",
        away: "法国",
        kickoff: "2026-11-13 03:45:00",
        pool: "had",
        sp: { home: 2.1, draw: 3.2, away: 3.4 },
        probs: { home: 0.45, draw: 0.3, away: 0.25 },
        gates: {},
      },
      lead: "完整判断在这里。",
    };
    const parsed = parseHomeMessages(JSON.stringify([prediction]));
    expect(parsed).toHaveLength(1);
    expect(parsed[0]).toMatchObject({
      kind: "prediction",
      lead: "完整判断在这里。",
      verdict: { id: "verdict-1" },
    });
  });

  it("summarizes TTL sections and top prediction", () => {
    const data: SportmonksIntelData = {
      league: "欧国联",
      predictionHighlights: [{
        key: "FULLTIME_RESULT_PROBABILITY",
        label: "全场胜平负",
        values: { home: 37.2, draw: 22.9, away: 39.9 },
      }],
      sections: { predictions: { capturedAt: "2026-11-12T13:20:12Z", ttlSeconds: 900 } },
    };
    const intel = summarizeIntel(data);
    expect(intel?.prediction).toContain("全场胜平负");
    expect(intel?.prediction).toContain("37%");
    expect(intel?.sections?.predictions).toBe("2026-11-12T13:20:12Z");
  });

  it("updates intel on match and prediction messages for the same match", () => {
    const prediction: HomeConversationMessage = {
      id: "p-1", kind: "prediction", at: 2, option: match.option,
      verdict: {
        id: "verdict-1", matchId: "match-1", matchNo: "周四001", league: "欧国联",
        home: "德国", away: "法国", kickoff: "2026-11-13 03:45:00", pool: "had",
        sp: { home: 2.1, draw: 3.2, away: 3.4 },
        probs: { home: 0.45, draw: 0.3, away: 0.25 }, gates: {},
      },
      lead: "完整判断在这里。",
    };
    const updated = updateHomeMatchIntel([match, prediction], "match-1", {
      injuries: [], homeForm: [], awayForm: [],
    });
    expect(updated[0]).toMatchObject({ intel: { injuries: [] } });
    expect(updated[1]).toMatchObject({ intel: { injuries: [] } });
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
