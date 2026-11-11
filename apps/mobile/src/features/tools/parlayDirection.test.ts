import { describe, expect, it } from "vitest";
import { toParlayDir } from "./parlayDirection";

describe("toParlayDir", () => {
  it("兼容后端中文方向", () => {
    expect(toParlayDir("主胜")).toBe("home");
    expect(toParlayDir("平")).toBe("draw");
    expect(toParlayDir("平局")).toBe("draw");
    expect(toParlayDir("客胜")).toBe("away");
  });

  it("兼容早期英文方向", () => {
    expect(toParlayDir("home")).toBe("home");
    expect(toParlayDir("draw")).toBe("draw");
    expect(toParlayDir("away")).toBe("away");
  });

  it("未知方向返回 null", () => {
    expect(toParlayDir(null)).toBeNull();
    expect(toParlayDir("观望")).toBeNull();
  });
});
