import type { GateKey } from "@/domain/types";
import { pct, pp } from "@/lib/format";

const ENGINE_LABEL: Record<string, string> = {
  goals_proxy: "xG 代理",
  xg: "xG",
  dixon_coles: "Dixon-Coles",
};

function humanizeReason(reason: string): string {
  if (reason.includes("the-odds-api") || reason.includes("国际盘源不足")) {
    return "国际盘还没覆盖这场，等数据源接入后会自动重评。";
  }
  if (reason.includes("xG") || reason.includes("队名未入")) {
    return "模型还没有这场的足够数据，暂不参与预测。";
  }
  return reason;
}

function sourceCount(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === "object") return Object.keys(value).length;
  return 0;
}

/**
 * 三关详情必须从真实 detail 字段生成：
 * - 市闸 sources 是对象（竞彩官方 + pinnacle），不是数组；
 * - 模闸通过时有 top/threshold，不能因为没有 reason 就显示“未覆盖”。
 */
export function gateDetailText(gate: GateKey, detail: Record<string, unknown>): string {
  if (gate === "price") {
    const rake = typeof detail.rake === "number" ? detail.rake : null;
    const threshold = typeof detail.threshold === "number" ? detail.threshold : null;
    return `${rake != null ? pct(rake) : "待同步"} / 阈值 ${threshold != null ? pct(threshold) : "待同步"}`;
  }
  if (gate === "market") {
    const count = sourceCount(detail.sources);
    const divergence = typeof detail.divergence === "number" ? detail.divergence : null;
    const threshold = typeof detail.threshold === "number" ? detail.threshold : null;
    if (count > 0) {
      const sourceLabel = count === 1 ? "单源" : `${count} 源`;
      return divergence != null
        ? `来源：${sourceLabel} · 离散 ${pp(divergence)} / 阈值 ${threshold != null ? pp(threshold) : "待同步"}`
        : `来源：${sourceLabel}`;
    }
    return typeof detail.reason === "string" ? humanizeReason(detail.reason) : "来源：待同步";
  }

  const top = typeof detail.top === "number" ? detail.top : null;
  const threshold = typeof detail.threshold === "number" ? detail.threshold : null;
  if (top != null) {
    const engine = typeof detail.engine_source === "string"
      ? ENGINE_LABEL[detail.engine_source] ?? detail.engine_source
      : null;
    return `收缩后最高 ${pct(top)} / 可推线 ${threshold != null ? pct(threshold) : "待同步"}${
      engine ? ` · ${engine}` : ""
    }`;
  }
  return typeof detail.reason === "string" ? humanizeReason(detail.reason) : "模型数据未覆盖";
}
