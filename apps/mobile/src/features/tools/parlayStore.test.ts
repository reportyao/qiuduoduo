import { beforeEach, describe, expect, it } from "vitest";
import { PARLAY_MAX_LEGS, useParlayStore, type ParlayLeg } from "./parlayStore";

const makeLeg = (index: number): ParlayLeg => ({
  verdictId: `v${index}`,
  matchId: `m${index}`,
  tradeDate: "2026-11-11",
  home: `主队${index}`,
  away: `客队${index}`,
  kickoff: "2026-11-11 20:00:00",
  dir: "home",
  odds: 2,
  rake: 0.03,
  marketOnly: false,
});

describe("parlayStore", () => {
  beforeEach(() => useParlayStore.getState().clear());

  it("上限 6 腿，第 7 腿被拒绝", () => {
    for (let i = 0; i < PARLAY_MAX_LEGS; i += 1) {
      expect(useParlayStore.getState().add(makeLeg(i)).ok).toBe(true);
    }
    const result = useParlayStore.getState().add(makeLeg(99));
    expect(result.ok).toBe(false);
    expect(result.reason).toContain("6");
    expect(useParlayStore.getState().legs).toHaveLength(PARLAY_MAX_LEGS);
  });

  it("同一场不能重复加入", () => {
    useParlayStore.getState().add(makeLeg(1));
    const result = useParlayStore.getState().add(makeLeg(1));
    expect(result.ok).toBe(false);
    expect(useParlayStore.getState().legs).toHaveLength(1);
  });

  it("移除与清空", () => {
    useParlayStore.getState().add(makeLeg(1));
    useParlayStore.getState().add(makeLeg(2));
    useParlayStore.getState().remove("v1");
    expect(useParlayStore.getState().legs.map((leg) => leg.verdictId)).toEqual(["v2"]);
    useParlayStore.getState().clear();
    expect(useParlayStore.getState().legs).toHaveLength(0);
  });
});
