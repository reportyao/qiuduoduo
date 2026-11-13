import type { SportmonksPredictionHighlight } from "@/domain/types";
import type { ProbabilityDatum } from "@/components/ui";

const OUTCOME: Record<string, string> = {
  home: "主胜", draw: "平局", away: "客胜",
};

const HTFT: Record<string, string> = {
  home_home: "主/主", home_draw: "主/平", home_away: "主/客",
  draw_home: "平/主", draw_draw: "平/平", draw_away: "平/客",
  away_home: "客/主", away_draw: "客/平", away_away: "客/客",
};

function labelFor(key: string, value: string): string {
  if (key === "BTTS_PROBABILITY") return value === "yes" ? "是" : value === "no" ? "否" : value;
  if (key.startsWith("OVER_UNDER_") || key.startsWith("HOME_OVER_UNDER_")
      || key.startsWith("AWAY_OVER_UNDER_")) {
    return value === "yes" ? "大" : value === "no" ? "小" : value;
  }
  if (key.startsWith("CORNERS_OVER_UNDER_")) {
    return { yes: "大", no: "小", over: "大", under: "小", equal: "走水" }[value] ?? value;
  }
  if (key === "DOUBLE_CHANCE_PROBABILITY") {
    return { draw_home: "主或平", draw_away: "平或客", home_away: "主或客" }[value] ?? value;
  }
  if (key === "TEAM_TO_SCORE_FIRST_PROBABILITY") {
    return { home: "主队先进", away: "客队先进", draw: "无进球" }[value] ?? value;
  }
  if (key === "HTFT_PROBABILITY") return HTFT[value] ?? value;
  if (value.startsWith("Other_")) return `其他 ${value.slice(6)}`;
  return OUTCOME[value] ?? value;
}

export interface PredictionDistribution {
  items: ProbabilityDatum[];
  predictedKey: string;
  predictedLabel: string;
  predictedValue: number;
}

/** 把 Sportmonks 的 25 维预测转成可排序、可视化的概率项。 */
export function predictionDistribution(
  item: SportmonksPredictionHighlight,
): PredictionDistribution {
  const raw = item.key === "CORRECT_SCORE_PROBABILITY"
    ? (item.scores ?? []).map((row) => ({ key: row.score, value: row.probability ?? 0 }))
    : Object.entries(item.values ?? {}).map(([key, value]) => ({ key, value: value ?? 0 }));
  const items = raw
    .filter((row) => row.value > 0)
    .sort((a, b) => b.value - a.value)
    .map((row) => ({
      key: row.key,
      label: item.key === "CORRECT_SCORE_PROBABILITY"
        ? (row.key.startsWith("Other") ? "其他比分" : row.key)
        : labelFor(item.key, row.key),
      value: row.value,
    }));
  const top = item.key === "CORRECT_SCORE_PROBABILITY"
    ? (items.find((row) => !row.key.startsWith("Other")) ?? items[0])
    : items[0];
  return {
    items,
    predictedKey: top?.key ?? "",
    predictedLabel: top?.label ?? "—",
    predictedValue: top?.value ?? 0,
  };
}
