import type { EvidenceItem, IntelDimension, IntelReport, VerdictDetail } from "./types";
import { array, number, record, string } from "@/lib/parse";

const DIMENSION_RULES: { key: string; label: string; keywords: string[] }[] = [
  { key: "motivation", label: "战意", keywords: ["战意", "排名", "保级", "欧战", "轮换"] },
  { key: "lineup", label: "阵容", keywords: ["阵容", "首发", "伤停", "缺阵", "停赛", "中卫"] },
  { key: "fatigue", label: "疲劳", keywords: ["疲劳", "赛程", "休息", "体能", "连续"] },
  { key: "form", label: "状态", keywords: ["状态", "xG", "近况", "势头", "射门"] },
];

function directionFromText(text: string): IntelDimension["direction"] {
  if (/缺|伤|停|不利|下降|疲劳|短/.test(text)) return "down";
  if (/回归|有利|提升|连续|稳定|跟上|确认/.test(text)) return "up";
  return "flat";
}

function dimensionValue(items: EvidenceItem[]): IntelDimension[] {
  return DIMENSION_RULES.map((rule) => {
    const hit = items.find((item) =>
      rule.keywords.some((keyword) => `${item.title}${item.detail}`.includes(keyword)),
    );
    if (!hit) {
      return {
        key: rule.key,
        label: rule.label,
        value: "未覆盖",
        direction: "unknown",
        note: "这个维度还没接入数据；不编结论。",
      };
    }
    const text = `${hit.title}：${hit.detail}`;
    return {
      key: rule.key,
      label: rule.label,
      value: hit.tag === "已计入" || hit.tag === "已核验" ? "已计入" : "仅背景",
      direction: directionFromText(text),
      note: text,
      source: hit.source,
    };
  });
}

function fromPayload(detail: VerdictDetail): IntelDimension[] | null {
  const intel = record(record(detail.payload).intel);
  const dimensions = array(intel.dimensions);
  if (dimensions.length === 0) return null;
  return dimensions.map((entry, index) => {
    const item = record(entry);
    return {
      key: string(item.key, `d${index}`),
      label: string(item.label, "情报"),
      value: string(item.value, "待定"),
      direction:
        item.direction === "up" || item.direction === "down" || item.direction === "flat"
          ? item.direction
          : "unknown",
      note: string(item.note),
      source: string(item.source) || undefined,
    };
  });
}

/**
 * 情报层适配：
 * 1) 后端若返回 payload.intel.dimensions，直接使用；
 * 2) 否则从已封存的 evidence 推导，明确区分「已计入 / 仅背景 / 未覆盖」；
 * 3) 绝不为了 UI 丰富度编造伤停或战意。
 */
export function buildIntelReport(detail: VerdictDetail): IntelReport {
  const payloadIntel = record(record(detail.payload).intel);
  const dimensions = fromPayload(detail) ?? dimensionValue(detail.evidence);
  const unPriced = detail.evidence.filter((item) => /未定价|not.?priced/i.test(item.tag)).length;
  const priced = detail.evidence.filter((item) => /已核验|已计入/.test(item.tag)).length;
  const pendingGate = (["market", "model"] as const).find(
    (gate) => detail.gates[gate] === "pending_data",
  );
  const gateName = pendingGate === "market" ? "国际盘" : pendingGate === "model" ? "模型" : "";
  const headline =
    string(payloadIntel.headline) ||
    (detail.status === "promoted"
      ? "三关已过，情报已封存"
      : pendingGate
        ? `还在等${gateName}数据`
        : "情报已收齐，结论见下");
  const summary =
    string(payloadIntel.summary) ||
    (detail.status === "promoted"
      ? `模型与市场方向一致。共 ${detail.evidence.length} 条依据，其中 ${priced} 条已计入判断。`
      : `当前没有足够数据把这场算清楚。已记录 ${detail.evidence.length} 条依据，${unPriced} 条尚未定价。`);
  return {
    headline,
    summary,
    dimensions,
    unPriced,
    total: number(payloadIntel.total, detail.evidence.length),
    cutoff: string(payloadIntel.data_cutoff, detail.dataCutoff),
    sourceCount: number(payloadIntel.source_count, new Set(detail.evidence.map((e) => e.source)).size),
    isFallback: !string(payloadIntel.headline),
  };
}
