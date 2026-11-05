import { describe, expect, it } from "vitest";
import { gateDetailText } from "./gateText";

describe("gateDetailText", () => {
  it("renders a passed model gate from top/threshold instead of claiming no coverage", () => {
    const text = gateDetailText("model", {
      top: 0.6153,
      threshold: 0.53,
      engine_source: "goals_proxy",
    });
    expect(text).toContain("61.5%");
    expect(text).toContain("53.0%");
    expect(text).toContain("xG 代理");
    expect(text).not.toContain("未覆盖");
  });

  it("counts market sources whether the API returns an object or an array", () => {
    expect(gateDetailText("market", {
      sources: { sp: [0.5, 0.25, 0.25], pinnacle: [0.51, 0.24, 0.25] },
      divergence: 0.0202,
      threshold: 0.05,
    })).toContain("2 源");
    expect(gateDetailText("market", { sources: ["a", "b"], divergence: 0.02, threshold: 0.05 }))
      .toContain("2 源");
  });

  it("keeps human-readable pending reasons", () => {
    expect(gateDetailText("model", { reason: "xG 队名未入表" })).toContain("模型还没有这场");
    expect(gateDetailText("market", {})).toBe("来源：待同步");
  });
});
