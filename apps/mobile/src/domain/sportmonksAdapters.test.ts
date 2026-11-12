import { describe, expect, it } from "vitest";
import { adaptSportmonksIntel } from "./sportmonksAdapters";

describe("sportmonks intel adapter", () => {
  it("parses lineups, standings, h2h and markets", () => {
    const data = adaptSportmonksIntel({
      fixture_id: 1,
      league: "欧国联",
      captured_at: "2026-11-12T12:00:00",
      lineups: {
        home: {
          team_name: "主队", formation: "4-4-2",
          starters: [{ player_id: 1, name: "甲", number: 1, position: "门将" }],
        },
        away: {
          team_name: "客队", formation: "4-3-3",
          starters: [{ player_id: 2, name: "乙", number: 9, position: "前锋" }],
        },
      },
      standings: {
        home: { position: 2, points: 6, played: 3, won: 2, form: ["W", "D"] },
        away: { position: 1, points: 9, played: 3, won: 3, form: ["W", "W"] },
      },
      h2h: [{
        date: "2026-10-01", home: "主队", away: "客队",
        score_home: 1, score_away: 3, result: "away",
      }],
      prediction_highlights: {
        items: [{
          key: "BTTS_PROBABILITY", label: "双方进球",
          values: { yes: 61.5, no: 38.5 },
        }],
      },
      market_board: [{
        key: "ou", name: "大小球", bookmaker: "Pinnacle", line: "2.5",
        selections: [{ label: "大", price: 1.9, probability: 52.6 }],
      }],
    });
    expect(data?.lineups?.home?.formation).toBe("4-4-2");
    expect(data?.lineups?.home?.starters[0].name).toBe("甲");
    expect(data?.standings?.away?.points).toBe(9);
    expect(data?.h2h?.[0].scoreAway).toBe(3);
    expect(data?.predictionHighlights?.[0].values?.yes).toBe(61.5);
    expect(data?.marketBoard?.[0].selections[0].price).toBe(1.9);
  });

  it("returns null for malformed input without throwing", () => {
    expect(adaptSportmonksIntel(null)).toBeNull();
    expect(adaptSportmonksIntel({ lineups: { home: {} } })?.lineups?.home).toBeUndefined();
  });
});
