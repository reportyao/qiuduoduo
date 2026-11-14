import { StyleSheet, View } from "react-native";
import { Card, Text } from "@/components/ui";
import type { ProbabilityCompareData, ProbabilityTriple } from "@/domain/types";
import { colors, radii, spacing } from "@/theme/tokens";

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function Row({
  label,
  probs,
  tone,
  delta,
}: {
  label: string;
  probs: ProbabilityTriple;
  tone: string;
  delta?: number;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowTop}>
        <Text variant="small" color={colors.muted}>{label}</Text>
        <View style={styles.rowRight}>
          {delta != null ? (
            <Text variant="caption" color={colors.amber}>分歧 {delta.toFixed(1)}pp</Text>
          ) : null}
          <Text variant="smallStrong" mono>{pct(probs.home)} / {pct(probs.draw)} / {pct(probs.away)}</Text>
        </View>
      </View>
      <View style={styles.bar}>
        <View style={[styles.seg, { flex: Math.max(probs.home, 0.01), backgroundColor: tone }]} />
        <View style={[styles.seg, { flex: Math.max(probs.draw, 0.01), backgroundColor: colors.lineStrong }]} />
        <View style={[styles.seg, { flex: Math.max(probs.away, 0.01), backgroundColor: colors.amber }]} />
      </View>
    </View>
  );
}

function divergence(a?: ProbabilityTriple | null, b?: ProbabilityTriple | null): number | undefined {
  if (!a || !b) return undefined;
  const values = [
    Math.abs(a.home - b.home),
    Math.abs(a.draw - b.draw),
    Math.abs(a.away - b.away),
  ];
  return Math.max(...values) * 100;
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text variant="caption" color={colors.muted}>{label}</Text>
    </View>
  );
}

/**
 * 概率对比：只在后端真的返回 probability_compare 时渲染。
 * 各条曲线分别标注数据名称，不把不同来源混成一条。
 */
export function ProbabilityCompareCard({ data }: { data: ProbabilityCompareData }) {
  const hasAny = Boolean(data.sp || data.model || data.market || data.thirdParty);
  if (!hasAny) return null;
  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <Text variant="h3">概率对比</Text>
        <View style={styles.legend}>
          <Legend color={colors.brand} label="主胜" />
          <Legend color={colors.lineStrong} label="平局" />
          <Legend color={colors.amber} label="客胜" />
        </View>
      </View>

      {data.sp ? (
        <Row
          label="竞彩隐含"
          probs={data.sp}
          tone={colors.brand}
          delta={divergence(data.model ?? data.thirdParty?.probs, data.sp)}
        />
      ) : null}
      {data.model ? (
        <Row
          label="模型概率"
          probs={data.model}
          tone={colors.ink}
          delta={divergence(data.model, data.market?.probs ?? data.thirdParty?.probs)}
        />
      ) : null}
      {data.market ? (
        <Row
          label="市场概率"
          probs={data.market.probs}
          tone={colors.muted}
          delta={divergence(data.sp, data.market.probs)}
        />
      ) : null}
      {data.thirdParty ? (
        <Row label="多维预测" probs={data.thirdParty.probs} tone={colors.amber} />
      ) : null}
      {data.dataCutoff ? (
        <Text variant="caption" color={colors.subtle} style={styles.note}>
          数据截至 {data.dataCutoff}
        </Text>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base, gap: spacing.sm },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  row: { gap: spacing.xs },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: spacing.sm },
  rowRight: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm },
  legend: { flexDirection: "row", gap: spacing.sm },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 4 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  bar: {
    flexDirection: "row",
    height: 8,
    borderRadius: radii.pill,
    overflow: "hidden",
    backgroundColor: colors.surfaceSunken,
  },
  seg: { height: "100%" },
  note: { lineHeight: 17 },
});
