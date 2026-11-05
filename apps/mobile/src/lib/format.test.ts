import { describe, expect, it } from "vitest";
import {
  countdownText,
  decimalToFormat,
  formatDate,
  formatTime,
  money,
  parseCnDateTime,
  pickDirectionLabel,
  shortHash,
  signedMoney,
  utcIso,
  weekdayCn,
  tradeDateCnFromKickoff,
  currentTradeDateCn,
  shiftDateCn,
} from "./format";

describe("parseCnDateTime", () => {
  it("parses backend CN naive strings at +08:00", () => {
    const d = parseCnDateTime("2026-11-04 04:00:00");
    expect(d?.toISOString()).toBe("2026-11-03T20:00:00.000Z");
    expect(formatTime("2026-11-04 04:00:00")).toBe("04:00");
    expect(formatDate("2026-11-04 04:00:00")).toBe("11月4日");
  });

  it("does not shift timestamps that already carry a zone", () => {
    const d = parseCnDateTime("2026-11-03T20:00:00.000Z");
    expect(d?.toISOString()).toBe("2026-11-03T20:00:00.000Z");
  });
});

describe("utcIso", () => {
  it("marks naive UTC fields with Z", () => {
    expect(utcIso("2026-11-02T21:21:00.428283")).toBe("2026-11-02T21:21:00.428283Z");
    expect(utcIso("2026-11-02T21:21:00+08:00")).toBe("2026-11-02T21:21:00+08:00");
  });
});

describe("countdownText", () => {
  const now = new Date("2026-11-03T20:00:00.000Z").getTime(); // 11-04 04:00 CN
  it("shows minutes/hours and closed state", () => {
    expect(countdownText("2026-11-04 05:30:00", now)).toBe("1 小时 30 分");
    expect(countdownText("2026-11-04 04:30:00", now)).toBe("30 分钟");
    expect(countdownText("2026-11-04 03:00:00", now)).toBe("已停售");
  });
});

describe("money display", () => {
  it("does not mark zero as a gain or a loss", () => {
    expect(signedMoney(0)).toBe("¥0");
    expect(signedMoney(12)).toBe("+¥12");
    expect(signedMoney(-12)).toBe("-¥12");
    expect(money(0)).toBe("¥0");
  });
});

describe("odds display", () => {
  it("formats decimal into all four conventions", () => {
    expect(decimalToFormat(2.05, "decimal")).toBe("2.05");
    expect(decimalToFormat(2.05, "hk")).toBe("1.05");
    expect(decimalToFormat(1.8, "indo")).toBe("-1.25");
    expect(decimalToFormat(2.05, "american")).toBe("+105");
  });
});

describe("trade dates", () => {
  it("uses the 05:00 CN trade-day boundary", () => {
    expect(tradeDateCnFromKickoff("2026-11-04 02:00:00")).toBe("2026-11-03");
    expect(tradeDateCnFromKickoff("2026-11-04 04:59:00")).toBe("2026-11-03");
    expect(tradeDateCnFromKickoff("2026-11-04 05:00:00")).toBe("2026-11-04");
    expect(currentTradeDateCn(new Date("2026-11-03T18:30:00Z").getTime())).toBe("2026-11-03");
    expect(currentTradeDateCn(new Date("2026-11-03T21:30:00Z").getTime())).toBe("2026-11-04");
    expect(shiftDateCn("2026-11-04", -1)).toBe("2026-11-03");
  });
});

describe("labels", () => {
  it("maps directions with handicap pool", () => {
    expect(pickDirectionLabel("hhad", "home")).toBe("让球主胜");
    expect(pickDirectionLabel("had", "home")).toBe("主胜");
    expect(pickDirectionLabel("hhad", "主胜")).toBe("让球主胜");
    expect(pickDirectionLabel("hhad", "平局")).toBe("让球平");
    expect(pickDirectionLabel("hhad", "客胜")).toBe("让球客胜");
    expect(pickDirectionLabel("had", null)).toBe("未给方向");
  });

  it("shortens hashes without losing ends", () => {
    expect(shortHash("abcdef1234567890")).toBe("abcdef12…7890");
  });

  it("names CN weekdays", () => {
    expect(weekdayCn("2026-11-04 04:00:00")).toBe("周三");
  });
});
