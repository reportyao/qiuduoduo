import { describe, expect, it } from "vitest";
import { ledgerStatusLabel } from "./ledgerStatus";

describe("ledgerStatusLabel", () => {
  it("labels publication status separately from settlement", () => {
    expect(ledgerStatusLabel("promoted")).toBe("通过三关");
    expect(ledgerStatusLabel("killed")).toBe("未给预测");
    expect(ledgerStatusLabel("screening")).toBe("复核中");
    expect(ledgerStatusLabel("unknown")).toBe("未定");
  });
});
