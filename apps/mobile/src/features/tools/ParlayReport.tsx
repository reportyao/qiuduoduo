import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Card, Chip, Divider, Text } from "@/components/ui";
import type { ParlayCheck, ParlayNote } from "./queries";
import type { OddsFormat } from "@/features/preferences/prefsStore";
import { decimalToFormat, money, oddsFormatLabel, pct } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";

const SCORE_LABEL: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  good: "完整",
  partial: "部分",
  weak: "不足",
  missing: "缺失",
};

const SCORE_TONE: Record<string, "green" | "amber" | "danger"> = {
  low: "green",
  good: "green",
  medium: "amber",
  partial: "amber",
  high: "danger",
  weak: "danger",
  missing: "danger",
};

const MISSING_LABEL: Record<string, string> = {
  price: "价格新鲜度",
  market: "国际盘",
  model: "模型",
  lineups: "首发",
  standings: "积分榜",
  sportmonks_intel: "第三方情报",
};

const STATUS_LABEL: Record<string, string> = {
  promoted: "三关全过",
  screening: "复核中",
  killed: "未给预测",
};

const FACT_STATUS: Record<string, string> = {
  confirmed: "已确认",
  inferred: "模型推断",
  stale: "已过期",
  unknown: "未知",
};

const GATE_LABEL: Record<string, string> = {
  price: "价",
  market: "市",
  model: "模",
};

function Score({ label, value }: { label: string; value: string }) {
  const tone = SCORE_TONE[value] ?? "amber";
  return (
    <View style={styles.score}>
      <Text variant="caption" color={colors.muted}>{label}</Text>
      <Chip label={SCORE_LABEL[value] ?? value} tone={tone} />
    </View>
  );
}

function Notes({ title, items }: { title: string; items: ParlayNote[] }) {
  if (items.length === 0) return null;
  return (
    <Card style={styles.block}>
      <Text variant="captionStrong" color={colors.muted}>{title}</Text>
      <View style={styles.notes}>
        {items.map((item) => (
          <View key={item.key} style={styles.noteRow}>
            <View
              style={[
                styles.noteDot,
                { backgroundColor: item.level === "high" ? colors.danger
                  : item.level === "medium" ? colors.amber : colors.green },
              ]}
            />
            <Text variant="small" color={colors.ink} style={styles.noteText}>
              {item.message}
            </Text>
          </View>
        ))}
      </View>
    </Card>
  );
}

function LegCard({ leg, index, oddsFormat }: {
  leg: ParlayCheck["legs"][number];
  index: number;
  oddsFormat: OddsFormat;
}) {
  const [open, setOpen] = useState(false);
  const edge = leg.model_edge;
  return (
    <Card style={styles.block}>
      <View style={styles.legHead}>
        <View style={styles.flex}>
          <Text variant="bodyStrong" numberOfLines={1}>
            {index + 1}. {leg.home} vs {leg.away}
          </Text>
          <Text variant="caption" color={colors.muted}>
            {leg.match_no} · {leg.dir_label} · {STATUS_LABEL[leg.status] ?? leg.status}
          </Text>
        </View>
        <Chip label={leg.coverage.level === "full" ? "信息全" : leg.coverage.level === "partial" ? "信息部分" : "信息不足"}
              tone={leg.coverage.level === "full" ? "green" : leg.coverage.level === "partial" ? "amber" : "danger"} />
      </View>

      <View style={styles.legRow}>
        <Text variant="caption" color={colors.muted}>价</Text>
        <Text variant="small" style={styles.flex}>
          {decimalToFormat(leg.odds, oddsFormat)} · 抽水 {pct(leg.rake)} · 市场 {pct(leg.market_prob)}
        </Text>
      </View>
      <View style={styles.legRow}>
        <Text variant="caption" color={colors.muted}>信</Text>
        <Text variant="small" style={styles.flex}>
          {leg.coverage.missing.length
            ? `缺 ${leg.coverage.missing.map((x) => MISSING_LABEL[x] ?? x).join(" / ")}`
            : "核心来源齐全"}
          {leg.facts.length ? ` · ${leg.facts.length} 条事实` : ""}
        </Text>
      </View>
      <View style={styles.legRow}>
        <Text variant="caption" color={colors.muted}>预</Text>
        <Text variant="small" style={styles.flex} color={leg.model_prob == null ? colors.amber : colors.ink}>
          {leg.model_prob == null
            ? "模型未覆盖，无法比较预测与市场"
            : `模型 ${pct(leg.model_prob)} vs 市场 ${pct(leg.market_prob)}${edge == null ? "" : `（${edge >= 0 ? "+" : ""}${(edge * 100).toFixed(1)}pp）`}`}
        </Text>
      </View>

      {leg.unknowns.length ? (
        <Text variant="caption" color={colors.amber} numberOfLines={2}>
          未知：{leg.unknowns.join(" · ")}
        </Text>
      ) : null}

      <Pressable onPress={() => setOpen((v) => !v)} hitSlop={8} accessibilityRole="button">
        <Text variant="captionStrong" color={colors.green}>
          {open ? "收起依据" : "展开依据"}
        </Text>
      </Pressable>
      {open ? (
        <View style={styles.evidence}>
          {leg.facts.slice(0, 6).map((fact) => (
            <View key={fact.id} style={styles.factRow}>
              <Text variant="captionStrong" color={colors.ink}>{fact.label}</Text>
              <Text variant="caption" color={colors.muted}>
                {fact.value} · {fact.source || "—"} · {FACT_STATUS[fact.status] ?? fact.status}
              </Text>
            </View>
          ))}
          <Divider />
          <Text variant="caption" color={colors.muted}>
            三闸：{Object.entries(leg.gates).map(([k, v]) => `${GATE_LABEL[k] ?? k}=${v}`).join(" · ") || "—"}
          </Text>
        </View>
      ) : null}
    </Card>
  );
}

export function ParlayReport({ data, oddsFormat }: {
  data: ParlayCheck;
  oddsFormat: OddsFormat;
}) {
  const { combo, scores } = data;
  return (
    <View style={styles.wrap}>
      <Text variant="h3">体检结果</Text>
      <Card tone="green" style={styles.block}>
        <Text variant="small" style={styles.summary}>{data.summary}</Text>
        <View style={styles.scores}>
          <Score label="成本" value={scores.cost} />
          <Score label="信息" value={scores.info} />
          <Score label="模型" value={scores.model} />
          <Score label="结构" value={scores.structure} />
        </View>
      </Card>

      <Text variant="captionStrong" color={colors.muted}>逐腿体检</Text>
      {data.legs.map((leg, index) => (
        <LegCard key={leg.verdict_id} leg={leg} index={index} oddsFormat={oddsFormat} />
      ))}

      <Card style={styles.block}>
        <Text variant="captionStrong" color={colors.muted}>组合数学</Text>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>组合赔率</Text><Text variant="bodyStrong">{decimalToFormat(combo.odds, oddsFormat)}</Text></View>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>市场隐含概率</Text><Text variant="bodyStrong">{pct(combo.market_prob)}</Text></View>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>模型组合概率</Text><Text variant="bodyStrong" color={combo.model_prob == null ? colors.amber : colors.ink}>{combo.model_prob == null ? `不完整（${combo.model_coverage}）` : pct(combo.model_prob)}</Text></View>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>模型 vs 市场</Text><Text variant="bodyStrong">{combo.model_edge == null ? "—" : `${combo.model_edge >= 0 ? "+" : ""}${(combo.model_edge * 100).toFixed(1)}pp`}</Text></View>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>抽水成本</Text><Text variant="bodyStrong" color={colors.danger}>{money(combo.cost, 2)}</Text></View>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>市场期望返还</Text><Text variant="bodyStrong">{money(combo.market_expected_return, 2)}</Text></View>
        <View style={styles.mathRow}><Text variant="small" color={colors.muted}>模型期望返还</Text><Text variant="bodyStrong">{combo.model_expected_return == null ? "—" : money(combo.model_expected_return, 2)}</Text></View>
        <Text variant="caption" color={colors.subtle}>
          模型概率是统计估计，不是命中承诺；组合按独立假设相乘，同联赛/同时段存在相关性。当前赔率格式：{oddsFormatLabel(oddsFormat)}。
        </Text>
      </Card>

      <Notes title="结构风险" items={data.risks} />
      <Notes title="可优化项" items={data.optimizations} />

      <Text variant="caption" color={colors.subtle} style={styles.footnote}>
        数据截至 {data.data_cutoff || data.as_of}。体检只做成本/信息/模型/结构分析，不构成投注建议。
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, marginTop: spacing.x4 },
  block: { gap: spacing.sm },
  summary: { lineHeight: 21 },
  scores: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  score: {
    flex: 1,
    minWidth: 68,
    gap: spacing.xxs,
    padding: spacing.sm,
    borderRadius: radii.sm,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  legHead: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  flex: { flex: 1 },
  legRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  evidence: { gap: spacing.xs, marginTop: spacing.xs },
  factRow: { gap: 1 },
  mathRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.sm },
  notes: { gap: spacing.sm },
  noteRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  noteDot: { width: 6, height: 6, borderRadius: 3, marginTop: 6 },
  noteText: { flex: 1, lineHeight: 19 },
  footnote: { lineHeight: 17, marginBottom: spacing.x4 },
});
