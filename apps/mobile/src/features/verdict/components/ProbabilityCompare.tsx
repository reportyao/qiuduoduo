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
 * 没有模型就明确标“模型未启用”，不把市场参考当模型。
 */
export function ProbabilityCompareCard({ data }: { data: ProbabilityCompareData }) {
  const hasAny = Boolean(data.sp || data.model || data.market);
  if (!hasAny) return null;
  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <Text variant="h3">概率对比</Text>
        <Text
          variant="caption"
          color={data.modelStatus === "enabled" ? colors.green : colors.amber}
        >
          {data.modelStatus === "enabled"
            ? "模型已启用"
            : data.modelEnabled ? "模型影子（未验证）" : "模型未启用"}
        </Text>
      </View>

      {data.sp ? <Row label="竞彩隐含" probs={data.sp} tone={colors.green} /> : null}
      {data.model ? (
        <Row label={data.modelStatus === "enabled" ? "融合模型" : "自有模型（影子）"}
          probs={data.model} tone={colors.greenDark} />
      ) : null}
      {data.market ? (
        <Row label={`市场 · ${data.market.bookmaker}`} probs={data.market.probs} tone={colors.muted} />
      ) : null}
      {data.thirdParty ? (
        <Row label={`第三方参考 · ${data.thirdParty.source}`} probs={data.thirdParty.probs} tone={colors.amber} />
      ) : null}

      {data.thirdParty ? (
        <Text variant="caption" color={colors.subtle} style={styles.note}>
          第三方参考不是本产品模型，也不代表已通过模型闸。
        </Text>
      ) : null}
      {!data.modelEnabled && !data.model ? (
        <Text variant="caption" color={colors.subtle} style={styles.note}>
          {data.reason || "该联赛模型未启用；以上只展示竞彩与市场参考。"}
        </Text>
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
