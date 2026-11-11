import { describe, expect, it } from "vitest";
import { adaptStream, adaptVerdictDetail, adaptWhyNot } from "./streamAdapters";

describe("adaptVerdictDetail", () => {
  it("parses probability_compare when backend provides it", () => {
    const detail = adaptVerdictDetail({
      id: "v2",
      trade_date: "2026-11-11",
      match_no: "周三002",
      league: "英超",
      home: "甲",
      away: "乙",
      kickoff: "2026-11-11 20:00:00",
      pool: "had",
      sp: { h: 2, d: 3, a: 4 },
      probs: { home: 0.5, draw: 0.3, away: 0.2 },
      rake: 0.03,
      status: "promoted",
      gates: {},
      pick: { dir: "主胜" },
      payload_hash: "b".repeat(64),
      created_at: "2026-11-11T12:00:00",
      probability_compare: {
        sp: { home: 0.48, draw: 0.31, away: 0.21 },
        model: { home: 0.52, draw: 0.28, away: 0.2 },
        market: { bookmaker: "Pinnacle", probs: { home: 0.5, draw: 0.29, away: 0.21 } },
        model_enabled: true,
        data_cutoff: "2026-11-11T12:00:00+08:00",
      },
      payload: { match_id: "2043001" },
    });
    expect(detail?.probabilityCompare?.model?.home).toBe(0.52);
    expect(detail?.probabilityCompare?.market?.bookmaker).toBe("Pinnacle");
    expect(detail?.probabilityCompare?.modelEnabled).toBe(true);
  });

  it("reads match_id from payload and gate objects", () => {
    const detail = adaptVerdictDetail({
      id: "v1",
      trade_date: "2026-11-04",
      match_no: "周三001",
      league: "英超",
      home: "甲",
      away: "乙",
      kickoff: "2026-11-04 04:00:00",
      pool: "hhad",
      goal_line: "-1",
      sp: { h: 1.85, d: 3.6, a: 3.9 },
      probs: { home: 0.58, draw: 0.24, away: 0.18 },
      rake: 0.09,
      status: "promoted",
      gates: {
        price: { gate: "price", result: "pass", detail: { rake: 0.09, threshold: 0.13 } },
        market: { gate: "market", result: "pass", detail: { divergence: 0.021 } },
        model: { gate: "model", result: "pass", detail: { top: 0.542 } },
      },
      pick: { dir: "home", prob: 0.58, sp: 1.85 },
      payload_hash: "a".repeat(64),
      sealed_at: "2026-11-02T21:21:00.428283",
      created_at: "2026-11-02T21:20:00.000000",
      payload: {
        match_id: "2042505",
        rake_threshold: 0.13,
        data_cutoff: "2026-11-04T01:30:00+08:00",
        evidence: [{ tag: "已核验", t: "官方 SP", d: "1.85 / 3.60 / 3.90", src: "sporttery" }],
      },
    });
    expect(detail).not.toBeNull();
    expect(detail?.matchId).toBe("2042505");
    expect(detail?.gates.price).toBe("pass");
    expect(detail?.gates.market).toBe("pass");
    expect(detail?.rakeThreshold).toBe(0.13);
    expect(detail?.evidence).toHaveLength(1);
    expect(detail?.sealedAt).toBe("2026-11-02T21:21:00.428283Z");
  });
});

describe("adaptStream", () => {
  it("keeps avoid match_id and rest-day fields", () => {
    const stream = adaptStream({
      trade_date: "2026-11-04",
      mode: "normal",
      stats: { total: 1, price_fail: 1 },
      verdicts: [
        {
          id: "v1",
          match_id: "m1",
          home: "甲",
          away: "乙",
          status: "screening",
          gates: { price: "pass", market: "pending_data" },
        },
      ],
      avoid: [
        {
          match_id: "m2",
          match_no: "周三002",
          home: "丙",
          away: "丁",
          rake: 0.14,
          gate: "price",
          why: "抽水超阈值",
          verdict_id: "v2",
        },
      ],
    });
    expect(stream.verdicts[0].matchId).toBe("m1");
    expect(stream.avoid[0].matchId).toBe("m2");
    expect(stream.stats.total).toBe(1);
  });
});

describe("adaptWhyNot", () => {
  it("keeps pending kind and human-readable what-if", () => {
    const w = adaptWhyNot({
      status: "screening",
      verdict_id: "v1",
      match_no: "周三001",
      home: "甲",
      away: "乙",
      dead_gate: "market",
      verdict_kind: "pending",
      title: "复核中",
      gates: {
        price: { gate: "price", result: "pass", detail: { rake: 0.09 } },
        market: { gate: "market", result: "pending_data", detail: {} },
      },
      whatif: "国际盘收敛后自动重评",
      audit: { model_runs: [], verdict_hash: "h" },
    });
    expect(w.verdictId).toBe("v1");
    expect(w.verdictKind).toBe("pending");
    expect(w.deadGate).toBe("market");
    expect(w.gates.price).toBeTruthy();
  });
});
