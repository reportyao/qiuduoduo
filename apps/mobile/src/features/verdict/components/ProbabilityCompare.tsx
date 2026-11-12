import { StyleSheet, View } from "react-native";
import { Card, Text } from "@/components/ui";
import type { ProbabilityCompareData, ProbabilityTriple } from "@/domain/types";
import { colors, radii, spacing } from "@/theme/tokens";

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function Row({ label, probs, tone }: { label: string; probs: ProbabilityTriple; tone: string }) {
  return (
    <View style={styles.row}>
      <Text variant="caption" color={colors.muted} style={styles.rowLabel}>{label}</Text>
      <View style={styles.bar}>
        <View style={[styles.seg, { flex: Math.max(probs.home, 0.01), backgroundColor: tone }]} />
        <View style={[styles.seg, { flex: Math.max(probs.draw, 0.01), backgroundColor: colors.lineStrong }]} />
        <View style={[styles.seg, { flex: Math.max(probs.away, 0.01), backgroundColor: colors.amber }]} />
      </View>
      <Text variant="caption" color={colors.ink} style={styles.values}>
        {pct(probs.home)} / {pct(probs.draw)} / {pct(probs.away)}
      </Text>
    </View>
  );
}

/**
 * 概率对比：只在后端真的返回 probability_compare 时渲染。
 * 各条曲线分别标注数据名称，不把不同来源混成一条。
 */
export function ProbabilityCompareCard({ data }: { data: ProbabilityCompareData }) {
  const hasAny = Boolean(data.sp || data.model || data.market);
  if (!hasAny) return null;
  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <Text variant="h3">概率对比</Text>
        <Text variant="caption" color={colors.green}>预测概率</Text>
      </View>

      {data.sp ? <Row label="竞彩隐含" probs={data.sp} tone={colors.green} /> : null}
      {data.model ? (
        <Row label="模型" probs={data.model} tone={colors.greenDark} />
      ) : null}
      {data.market ? (
        <Row label="市场" probs={data.market.probs} tone={colors.muted} />
      ) : null}
      {data.thirdParty ? (
        <Row label="预测" probs={data.thirdParty.probs} tone={colors.amber} />
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
  rowLabel: { lineHeight: 16 },
  bar: {
    flexDirection: "row",
    height: 8,
    borderRadius: radii.pill,
    overflow: "hidden",
    backgroundColor: colors.surfaceSunken,
  },
  seg: { height: "100%" },
  values: { lineHeight: 16 },
  note: { lineHeight: 17 },
});
