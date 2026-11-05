import { describe, expect, it } from "vitest";
import type { FocusCoverage } from "@/domain/focusAdapters";
import { coverageGaps } from "./focusCoverage";

function coverage(overrides: Partial<FocusCoverage> = {}): FocusCoverage {
  return {
    score: 10,
    level: "insufficient",
    deepEligible: false,
    missing: ["price", "market", "model", "lineups", "standings"],
    sources: [
      { key: "price", status: "stale", lastSync: null, coverage: 0 },
      { key: "market", status: "stale", lastSync: null, coverage: 0 },
      { key: "model", status: "missing", lastSync: null, coverage: 0 },
      { key: "lineups", status: "missing", lastSync: null, coverage: 0 },
      { key: "standings", status: "missing", lastSync: null, coverage: 0 },
    ],
    minutesToClose: 120,
    hoursToKickoff: 2,
    ...overrides,
  };
}

describe("coverageGaps", () => {
  it("splits stale data from genuinely missing data and localizes labels", () => {
    expect(coverageGaps(coverage())).toEqual({
      stale: ["赔率", "国际盘"],
      missing: ["模型", "阵容", "积分榜"],
    });
  });

  it("treats a missing entry without a matching source as absent", () => {
    expect(coverageGaps(coverage({ missing: ["price"], sources: [] })).missing).toEqual(["赔率"]);
  });
});
