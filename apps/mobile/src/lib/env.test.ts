import { describe, expect, it } from "vitest";
import { devApiBaseUrl } from "./envDefaults";

describe("env defaults", () => {
  it("uses the Android emulator host on Android", () => {
    expect(devApiBaseUrl("android")).toBe("http://10.0.2.2:8100");
  });

  it("uses localhost on iOS and other platforms", () => {
    expect(devApiBaseUrl("ios")).toBe("http://127.0.0.1:8100");
    expect(devApiBaseUrl("web")).toBe("http://127.0.0.1:8100");
  });
});
