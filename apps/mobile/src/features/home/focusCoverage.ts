import type { FocusCoverage } from "@/domain/focusAdapters";

const LABELS: Record<string, string> = {
  price: "赔率",
  market: "市场数据",
  model: "模型",
  lineups: "阵容",
  standings: "积分榜",
  schedule: "赛程",
  sportmonks_intel: "第三方情报",
};

export interface CoverageGaps {
  /** 有数据但超过新鲜度阈值。 */
  stale: string[];
  /** 完全没有数据。 */
  missing: string[];
}

/**
 * coverage.missing 同时包含“没有数据”和“数据偏旧”；
 * 前端必须分开讲，否则会出现“价闸已过”却显示“缺赔率”的矛盾。
 */
export function coverageGaps(coverage: FocusCoverage): CoverageGaps {
  const status = new Map(coverage.sources.map((source) => [source.key, source.status]));
  const gaps: CoverageGaps = { stale: [], missing: [] };
  for (const key of coverage.missing) {
    const label = LABELS[key] ?? key;
    if (status.get(key) === "stale") gaps.stale.push(label);
    else gaps.missing.push(label);
  }
  return gaps;
}
