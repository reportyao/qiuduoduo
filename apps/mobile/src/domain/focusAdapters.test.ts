import { describe, expect, it } from "vitest";
import { adaptFocus, adaptPulse } from "./focusAdapters";

describe("focus adapters", () => {
  it("parses coverage, facts and capabilities", () => {
    const focus = adaptFocus({
      match: { match_id: "m1", match_no: "周三001", league: "英超", home: "曼城", away: "曼联", kickoff: "2026-11-05 20:00:00", sale_close: "2026-11-05 20:00:00" },
      state: "promoted",
      trade_date: "2026-11-05",
      request_id: "r1",
      as_of: "2026-11-05T12:00:00+08:00",
      coverage: { score: 70, level: "full", deep_eligible: true, missing: [], sources: [], minutes_to_close: 60, hours_to_kickoff: 1 },
      intel: { facts: [{ id: "f1", kind: "price", label: "SP", value: "1.80", status: "confirmed" }], unknowns: ["阵容"] },
      capabilities: { can_bet: false, bet_requires_confirm: false, can_watch: true, watching: false, can_why_not: false, can_view_detail: true, can_share: true, can_rest: true, can_remind_lineup: true, can_refresh: true },
      actions: [{ id: "bet", enabled: false, primary: true, requires_auth: true, reason: "rested" }],
      verdict: { id: "v1" },
    });
    expect(focus?.coverage.score).toBe(70);
    expect(focus?.facts[0].value).toBe("1.80");
    expect(focus?.actions[0].reason).toBe("rested");
    expect(focus?.verdictId).toBe("v1");
  });

  it("parses pulse real counts and display factor", () => {
    const pulse = adaptPulse({
      trade_date: "2026-11-05",
      as_of: "2026-11-05T12:00:00+08:00",
      counts: { matches: 9, sp_snapshots: 18, verdicts: 9 },
      data_points: 27,
      display: { data_points: 81, factor: 3, unit: "数据点" },
      all_time: { data_points: 100, matches: 10, sealed: 9 },
      stages: [],
      sources: [{ key: "price", label: "竞彩官方 SP", status: "ok", coverage: 1 }],
      outcomes: { promoted: 2, screening: 3, killed: 4 },
      excluded: 0,
      definition: "test",
    });
    expect(pulse.counts.matches).toBe(9);
    expect(pulse.display.dataPoints).toBe(81);
    expect(pulse.sources[0].status).toBe("ok");
  });
});
