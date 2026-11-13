import { describe, expect, it } from "vitest";
import {
  resultLabel,
  resultTone,
  scoreStatusLabel,
  splitPredictionItems,
  stateLabel,
} from "./labels";

describe("match board labels", () => {
  it("maps live states without inventing unknown ones", () => {
    expect(stateLabel("2H")).toBe("下半场");
    expect(stateLabel("HT")).toBe("中场");
    expect(stateLabel("XYZ")).toBe("XYZ");
  });

  it("keeps AET/PEN separate from FT90", () => {
    expect(scoreStatusLabel("FT")).toBe("FT");
    expect(scoreStatusLabel("AET")).toBe("加时");
    expect(scoreStatusLabel("PEN")).toBe("点球");
  });

  it("maps settlement results to tones", () => {
    expect(resultLabel("hit")).toBe("命中");
    expect(resultLabel("push")).toBe("走水");
    expect(resultTone("miss")).toBe("danger");
    expect(resultTone("insufficient_data")).toBe("neutral");
  });

  it("splits counted and reference dimensions", () => {
    const base = {
      source: "sportmonks",
      label: "",
      predicted_key: "yes",
      predicted_label: "大",
      predicted_probability: 0.6,
      market_line: "",
      actual_key: "yes",
      actual_label: "大",
      result: "hit",
    };
    const split = splitPredictionItems([
      { ...base, type: "BTTS_PROBABILITY", counted_in_accuracy: true },
      { ...base, type: "CORNERS_OVER_UNDER_5_PROBABILITY", counted_in_accuracy: false },
    ]);
    expect(split.counted).toHaveLength(1);
    expect(split.reference).toHaveLength(1);
  });
});
