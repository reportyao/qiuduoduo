import { StyleSheet, View } from "react-native";
import type { IntelReport } from "@/domain/types";
import { formatDateTime } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Card, Icon, Text } from "@/components/ui";

const DIRECTION: Record<string, { icon: "arrow-up" | "arrow-down" | "remove"; color: string }> = {
  up: { icon: "arrow-up", color: colors.green },
  down: { icon: "arrow-down", color: colors.danger },
  flat: { icon: "remove", color: colors.muted },
  unknown: { icon: "remove", color: colors.subtle },
};

export function IntelSection({ report }: { report: IntelReport }) {
  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <View style={styles.iconWrap}>
          <Icon name="sparkles" size={17} color={colors.green} />
        </View>
        <View style={styles.headText}>
          <Text variant="overline" color={colors.green}>AI 情报研判</Text>
          <Text variant="h3">{report.headline}</Text>
        </View>
      </View>
      <Text variant="small" color={colors.muted} style={styles.summary}>{report.summary}</Text>

      <View style={styles.grid}>
        {report.dimensions.map((dim) => {
          const tone = DIRECTION[dim.direction] ?? DIRECTION.unknown;
          return (
            <View key={dim.key} style={styles.tile}>
              <View style={styles.tileHead}>
                <Text variant="captionStrong">{dim.label}</Text>
                <View style={styles.valueRow}>
                  <Icon name={tone.icon} size={12} color={tone.color} />
                  <Text variant="captionStrong" color={tone.color}>{dim.value}</Text>
                </View>
              </View>
              <Text variant="caption" color={colors.muted} numberOfLines={2} style={styles.tileNote}>
                {dim.note}
              </Text>
            </View>
          );
        })}
      </View>

      <View style={styles.footer}>
        <Text variant="caption" color={colors.subtle}>
          依据 {report.total} 条 · 未定价 {report.unPriced} 条 · {report.sourceCount} 个来源
        </Text>
        <Text variant="caption" color={colors.subtle}>
          截止 {report.cutoff ? formatDateTime(report.cutoff) : "待同步"}
        </Text>
      </View>
      {report.isFallback ? (
        <Text variant="caption" color={colors.muted} style={styles.fallback}>
          当前数据库还没返回结构化四维情报；上面只展示已封存、可核验的依据，不补编伤停或战意。
        </Text>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base, gap: spacing.sm },
  head: { flexDirection: "row", gap: spacing.base, alignItems: "flex-start" },
  iconWrap: {
    width: 34,
    height: 34,
    borderRadius: 12,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  headText: { flex: 1, gap: 1 },
  summary: { lineHeight: 20 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.xs },
  tile: {
    width: "48.5%",
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    padding: spacing.base,
    gap: 4,
  },
  tileHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 4 },
  valueRow: { flexDirection: "row", alignItems: "center", gap: 2 },
  tileNote: { lineHeight: 16 },
  footer: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    paddingTop: spacing.sm,
    gap: 2,
  },
  fallback: { lineHeight: 17, marginTop: 2 },
});
