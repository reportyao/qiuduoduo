import { describe, expect, it } from "vitest";
import { onSaleStatusLabel } from "./onSaleStatus";

describe("onSaleStatusLabel", () => {
  it("distinguishes killed matches from live on-sale matches", () => {
    expect(onSaleStatusLabel("promoted")).toBe("已过");
    expect(onSaleStatusLabel("screening")).toBe("复核");
    expect(onSaleStatusLabel("killed")).toBe("已砍");
    expect(onSaleStatusLabel("on_sale")).toBe("在售");
    expect(onSaleStatusLabel("")).toBe("在售");
    expect(onSaleStatusLabel(null)).toBe("在售");
  });
});
