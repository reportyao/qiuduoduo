import { describe, expect, it } from "vitest";
import { ledgerStatusLabel } from "./ledgerStatus";

describe("ledgerStatusLabel", () => {
  it("labels publication status separately from settlement", () => {
    expect(ledgerStatusLabel("promoted")).toBe("过三关");
    expect(ledgerStatusLabel("killed")).toBe("已砍");
    expect(ledgerStatusLabel("screening")).toBe("复核中");
    expect(ledgerStatusLabel("unknown")).toBe("未定");
  });
});
