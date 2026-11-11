import { describe, expect, it } from "vitest";
import type { OnSaleItem, VerdictSummary } from "@/domain/types";
import { buildBriefOptions } from "./briefOptions";

const verdict = (over: Partial<VerdictSummary>): VerdictSummary => ({
  id: "v1",
  matchId: "m1",
  matchNo: "周三001",
  league: "英超",
  home: "主队",
  away: "客队",
  kickoff: "2026-11-11 20:00:00",
  pool: "had",
  goalLine: null,
  sp: { h: 2, d: 3, a: 4 },
  rake: 0.03,
  rakeThreshold: 0.05,
  probs: { home: 0.5, draw: 0.3, away: 0.2 },
  model: null,
  pick: null,
  status: "promoted",
  gates: {},
  hash: null,
  sealed: false,
  ...over,
});

const onsale = (over: Partial<OnSaleItem>): OnSaleItem => ({
  matchId: "m1",
  matchNo: "周三001",
  league: "英超",
  home: "主队",
  away: "客队",
  kickoff: "2026-11-11 20:00:00",
  saleClose: "2026-11-11 20:00:00",
  single: false,
  rake: null,
  gates: null,
  status: null,
  verdictId: null,
  coverage: null,
  ...over,
});

describe("buildBriefOptions", () => {
  it("同日合并去重，判决优先", () => {
    const options = buildBriefOptions(
      [verdict({ matchId: "m1", id: "v1" })],
      [],
      [onsale({ matchId: "m1", verdictId: null }), onsale({ matchId: "m2", home: "第二场", kickoff: "2026-11-11 22:00:00" })],
      "2026-11-11",
    );
    expect(options).toHaveLength(2);
    expect(options.find((item) => item.matchId === "m1")?.verdictId).toBe("v1");
  });

  it("过滤掉其他竞彩日的在售场次", () => {
    const options = buildBriefOptions(
      [],
      [],
      [onsale({ matchId: "m1" }), onsale({ matchId: "m2", kickoff: "2026-11-12 20:00:00" })],
      "2026-11-11",
    );
    expect(options.map((item) => item.matchId)).toEqual(["m1"]);
  });

  it("按开赛时间排序", () => {
    const options = buildBriefOptions(
      [],
      [],
      [onsale({ matchId: "late", kickoff: "2026-11-11 23:00:00" }), onsale({ matchId: "early", kickoff: "2026-11-11 18:00:00" })],
      "2026-11-11",
    );
    expect(options.map((item) => item.matchId)).toEqual(["early", "late"]);
  });
});

  it("市场参考会进入选场条并带 tier", () => {
    const options = buildBriefOptions(
      [],
      [verdict({ matchId: "ref1", id: "v-ref1", tier: "market_reference", status: "screening" })],
      [],
      "2026-11-11",
    );
    expect(options).toHaveLength(1);
    expect(options[0].tier).toBe("market_reference");
    expect(options[0].verdictId).toBe("v-ref1");
  });
