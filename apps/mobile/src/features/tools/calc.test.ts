import { describe, expect, it } from "vitest";
import {
  breakEvenMath,
  kellyMath,
  oddsMath,
  parlayMath,
  parseNumber,
  rakeMath,
} from "./calc";

describe("parlayMath", () => {
  it("multiplies odds and return rates", () => {
    const r = parlayMath(
      [
        { odds: 2.2, rake: 0.12 },
        { odds: 1.51, rake: 0.12 },
      ],
      100,
    );
    expect(r.comboOdds).toBeCloseTo(3.322, 3);
    expect(r.impliedProbability).toBeCloseTo(0.301, 3);
    expect(r.theoreticalReturnRate).toBeCloseTo(0.7744, 4);
    expect(r.expectedReturn).toBeCloseTo(77.44, 1);
    expect(r.expectedLoss).toBeCloseTo(22.56, 1);
  });
});

describe("rakeMath", () => {
  it("matches official overround formula", () => {
    const r = rakeMath([2.2, 4.4, 2.19]);
    expect(r.rake).toBeCloseTo(0.1216, 4);
    expect(r.returnRate).toBeCloseTo(0.8784, 4);
    expect(r.probs[0] + r.probs[1] + r.probs[2]).toBeCloseTo(1, 10);
    expect(r.fairOdds[0]).toBeCloseTo(2.5048, 3);
  });
});

describe("oddsMath", () => {
  it("converts decimal to HK/Indo/American", () => {
    expect(oddsMath(2.05).hk).toBeCloseTo(1.05, 2);
    expect(oddsMath(2.05).indo).toBeCloseTo(1.05, 2);
    expect(oddsMath(1.8).indo).toBeCloseTo(-1.25, 2);
    expect(oddsMath(2.05).american).toBeCloseTo(105, 0);
    expect(oddsMath(1.8).american).toBeCloseTo(-125, 0);
  });
});

describe("kellyMath", () => {
  it("caps at 5% bankroll and never returns negative stake", () => {
    const r = kellyMath({ bankroll: 1000, probability: 0.54, decimal: 2.05, fraction: 0.5 });
    expect(r.edge).toBeCloseTo(0.107, 3);
    expect(r.stake).toBeLessThanOrEqual(50);
    expect(r.capped).toBe(true);
    const negative = kellyMath({ bankroll: 1000, probability: 0.3, decimal: 2.0 });
    expect(negative.fullKelly).toBe(0);
    expect(negative.stake).toBe(0);
  });
});

describe("breakEvenMath", () => {
  it("computes win-rate threshold and P&L", () => {
    const r = breakEvenMath(1.95, 100);
    expect(r.winRate).toBeCloseTo(0.5128, 4);
    expect(r.profit).toBeCloseTo(95, 2);
    expect(r.expectedValue).toBeCloseTo(0, 10);
  });
});

describe("parseNumber", () => {
  it("tolerates currency and spaces", () => {
    expect(parseNumber("¥100")).toBe(100);
    expect(parseNumber(" 2.05 ")).toBe(2.05);
    expect(parseNumber("")).toBeNull();
  });
});
