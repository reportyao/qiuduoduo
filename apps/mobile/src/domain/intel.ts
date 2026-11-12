import type {
  EvidenceItem,
  IntelDimension,
  IntelReport,
  SportmonksIntelData,
  VerdictDetail,
} from "./types";
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
  const out: IntelDimension[] = [];
  for (const rule of DIMENSION_RULES) {
    const hit = items.find((item) =>
      rule.keywords.some((keyword) => `${item.title}${item.detail}`.includes(keyword)),
    );
    if (!hit) continue;
    const text = `${hit.title}：${hit.detail}`;
    out.push({
      key: rule.key,
      label: rule.label,
      value: /背景|未定价|未验证/.test(hit.tag) ? "数据" : "核心",
      direction: directionFromText(text),
      note: text,
      source: hit.source,
    });
  }
  return out;
}

function sportmonksDimensions(data?: SportmonksIntelData | null): IntelDimension[] {
  if (!data) return [];
  const out: IntelDimension[] = [];
  const home = data.standings?.home;
  const away = data.standings?.away;
  if (home || away) {
    out.push({
      key: "motivation",
      label: "战意",
      value: `${home?.position ?? "—"} / ${away?.position ?? "—"}`,
      direction: "flat",
      note: `积分榜：主队第 ${home?.position ?? "—"}（${home?.points ?? "—"} 分），客队第 ${away?.position ?? "—"}（${away?.points ?? "—"} 分）。`,
      source: "积分榜",
    });
  }
  const homeLine = data.lineups?.home;
  const awayLine = data.lineups?.away;
  if (homeLine?.starters?.length && awayLine?.starters?.length) {
    const injured = data.sidelined ?? [];
    out.push({
      key: "lineup",
      label: "阵容",
      value: "首发已公布",
      direction: injured.length > 0 ? "down" : "flat",
      note: `${homeLine.formation || "—"} / ${awayLine.formation || "—"}；${injured.length ? `伤停 ${injured.map((row) => row.playerName).slice(0, 3).join("、")}` : "暂无伤停记录"}`,
      source: "阵容",
    });
  }
  if (data.recent?.home?.length || data.recent?.away?.length) {
    const homeForm = data.recent?.home ?? [];
    const awayForm = data.recent?.away ?? [];
    const wins = [...homeForm, ...awayForm].filter((item) => item === "W").length;
    const losses = [...homeForm, ...awayForm].filter((item) => item === "L").length;
    out.push({
      key: "form",
      label: "状态",
      value: `${homeForm.slice(0, 4).join("") || "—"} / ${awayForm.slice(0, 4).join("") || "—"}`,
      direction: wins > losses ? "up" : losses > wins ? "down" : "flat",
      note: "近 5 场走势。",
      source: "近况",
    });
  }
  const venue = data.venue;
  const weather = data.weather;
  const referee = data.referees?.main;
  if (venue || weather || referee) {
    const temp = weather?.temperature?.day;
    out.push({
      key: "environment",
      label: "环境",
      value: weather?.description || referee?.name || venue?.city || "已同步",
      direction: "flat",
      note: [
        venue?.name ? `球场 ${venue.name}${venue.city ? `（${venue.city}）` : ""}` : "",
        temp != null ? `日间 ${temp}°C` : "",
        referee?.name ? `主裁 ${referee.name}` : "",
      ].filter(Boolean).join("；") || "环境数据已同步。",
      source: "环境",
    });
  }
  return out;
}

function mergeDimensions(base: IntelDimension[], extra: IntelDimension[]): IntelDimension[] {
  const byKey = new Map(base.map((item) => [item.key, item]));
  for (const item of extra) byKey.set(item.key, item);
  return [...byKey.values()];
}

function fromPayload(detail: VerdictDetail): IntelDimension[] | null {
  const intel = record(record(detail.payload).intel);
  const dimensions = array(intel.dimensions);
  if (dimensions.length === 0) return null;
  return dimensions
    .map((entry, index): IntelDimension => {
      const item = record(entry);
      return {
        key: string(item.key, `d${index}`),
        label: string(item.label, "情报"),
        value: /背景|未定价|未验证/.test(string(item.value)) ? "数据" : "核心",
        direction:
          item.direction === "up" || item.direction === "down" || item.direction === "flat"
            ? item.direction
            : "unknown",
        note: string(item.note),
        source: string(item.source) || undefined,
      };
    })
    .filter((item) => item.value !== "未覆盖" && item.note !== "数据待同步。");
}

/**
 * 情报层适配：
 * 1) 后端若返回 payload.intel.dimensions，直接使用；
 * 2) 否则从已封存的 evidence 推导，明确区分「已计入 / 仅背景 / 未覆盖」；
 * 3) 绝不为了 UI 丰富度编造伤停或战意。
 */
export function buildIntelReport(detail: VerdictDetail): IntelReport {
  const payloadIntel = record(record(detail.payload).intel);
  const dimensions = mergeDimensions(
    fromPayload(detail) ?? dimensionValue(detail.evidence),
    sportmonksDimensions(detail.sportmonksIntel),
  );
  const unPriced = detail.evidence.filter((item) => /未定价|not.?priced/i.test(item.tag)).length;
  const priced = detail.evidence.filter((item) => /已核验|已计入/.test(item.tag)).length;
  const headline =
    string(payloadIntel.headline) ||
    (detail.status === "promoted"
      ? detail.sealedAt ? "预测已封存" : "预测已生成"
      : detail.sportmonksIntel
        ? "阵容、形势与环境已同步"
        : "情报已同步，预测见下");
  const summary =
    string(payloadIntel.summary) ||
    (detail.status === "promoted"
      ? detail.evidence.length
        ? `共 ${detail.evidence.length} 条依据，其中 ${priced} 条已计入预测。`
        : "预测已生成，完整数据见下方。"
      : detail.evidence.length
        ? `已同步 ${detail.evidence.length} 条依据，完整数据见下方。`
        : "本场数据已同步，完整预测见下方。");
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
