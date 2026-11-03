import { describe, expect, it } from "vitest";
import { API_BASE_URL, APP_ENV } from "./env";

describe("env", () => {
  it("has an API base URL", () => {
    expect(API_BASE_URL).toMatch(/^https?:\/\//);
  });

  it("reports an app environment", () => {
    expect(APP_ENV.length).toBeGreaterThan(0);
  });
});
