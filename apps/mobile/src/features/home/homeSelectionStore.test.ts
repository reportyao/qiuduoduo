import { describe, expect, it } from "vitest";
import { useHomeSelectionStore } from "./homeSelectionStore";

const selection = {
  option: {
    matchId: "m1", verdictId: "v1", matchNo: "周四001", league: "欧国联",
    home: "黑山", away: "拉脱维亚", kickoff: "2026-11-13 03:45:00",
  },
  verdict: null,
  match: null,
  tradeDate: "2026-11-12",
};

describe("home selection handoff", () => {
  it("keeps a pending pick until the home screen consumes it", () => {
    useHomeSelectionStore.getState().request(selection);
    expect(useHomeSelectionStore.getState().pending?.option.matchId).toBe("m1");
    useHomeSelectionStore.getState().consume();
    expect(useHomeSelectionStore.getState().pending).toBeNull();
  });
});
