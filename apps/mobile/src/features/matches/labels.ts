import type { PredictionItem } from "./queries";

/** Sportmonks 短状态 → 中文。未知状态不猜，直接回原值。 */
export function stateLabel(state: string): string {
  const key = state.toUpperCase();
  const labels: Record<string, string> = {
    "1H": "上半场",
    HT: "中场",
    "2H": "下半场",
    ET: "加时",
    AET: "加时结束",
    PEN: "点球大战",
    FT: "全场",
    FINISHED: "完场",
    NS: "未开赛",
    PST: "延期",
    CANC: "取消",
    ABAN: "中断",
    SUSP: "暂停",
    LIVE: "进行中",
  };
  return labels[key] ?? state ?? "";
}

/** 比分旁的阶段说明；点球/加时只看 FT90 结算，页面上要标清口径。 */
export function scoreStatusLabel(status: string): string {
  const key = status.toUpperCase();
  if (key === "AET") return "加时";
  if (key === "PEN") return "点球";
  if (key === "FT" || key === "FINISHED") return "FT";
  return stateLabel(status);
}

export function resultLabel(result: string): string {
  return {
    hit: "命中",
    miss: "未中",
    push: "走水",
    insufficient_data: "待数据",
  }[result] ?? "待结算";
}

export function resultTone(result: string): "green" | "danger" | "amber" | "neutral" {
  if (result === "hit") return "green";
  if (result === "miss") return "danger";
  if (result === "push") return "amber";
  return "neutral";
}

/** 单场维度排序：计入命中率的排前面，其余保持后端顺序。 */
export function splitPredictionItems(items: PredictionItem[]): {
  counted: PredictionItem[];
  reference: PredictionItem[];
} {
  return {
    counted: items.filter((item) => item.counted_in_accuracy),
    reference: items.filter((item) => !item.counted_in_accuracy),
  };
}
