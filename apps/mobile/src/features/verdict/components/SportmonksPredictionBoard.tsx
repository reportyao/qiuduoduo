import { StyleSheet, useWindowDimensions, View } from "react-native";
import type { SportmonksMarketBoard, SportmonksPredictionHighlight } from "@/domain/types";
import { Button, Icon, ProbabilityBreakdown, Text } from "@/components/ui";
import { ageLabel } from "@/lib/freshness";
import { colors, radii, spacing } from "@/theme/tokens";
import { predictionDistribution } from "../predictionData";

/**
 * 完整预测板：Sportmonks 返回的 25 维预测 + 选定市场。
 * 非会员仍能看到入口和少量预览，但具体内容以遮罩锁定，避免直接暴露付费数据。
 */
export function SportmonksPredictionBoard({
  predictions = [],
  markets = [],
  capturedAt,
  locked = false,
  onUnlock,
}: {
  predictions?: SportmonksPredictionHighlight[];
  markets?: SportmonksMarketBoard[];
  capturedAt?: string | null;
  locked?: boolean;
  onUnlock?: () => void;
}) {
  const { width } = useWindowDimensions();
  const marketWidth = width >= 360 ? "48%" : "100%";
  if (!predictions.length && !markets.length) return null;
  const preview = locked ? predictions.slice(0, 3) : predictions;
  const total = predictions.length;
  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <View style={styles.headText}>
          <Text variant="h3">全部预测</Text>
          <Text variant="caption" color={colors.muted}>
            {total} 维 · {markets.length} 个市场
          </Text>
        </View>
        <Text variant="caption" color={colors.subtle}>{ageLabel(capturedAt)}</Text>
      </View>

      <View style={[styles.board, locked && styles.lockedBoard]}>
        <View style={[styles.rows, locked && styles.lockedRows]} pointerEvents="none">
          {preview.map((item, index) => {
            const dist = predictionDistribution(item);
            return (
              <View
                key={item.key}
                style={[styles.dim, index < preview.length - 1 && styles.dimLine]}
              >
                <View style={styles.dimHead}>
                  <Text variant="small" color={colors.muted} style={styles.flex} numberOfLines={1}>
                    {item.label}
                  </Text>
                  <Text variant="caption" color={colors.brand} numberOfLines={1}>
                    {dist.predictedLabel} {dist.predictedValue.toFixed(1)}%
                  </Text>
                </View>
                <ProbabilityBreakdown
                  items={dist.items}
                  predictedKey={dist.predictedKey}
                />
              </View>
            );
          })}
        </View>

        {locked ? (
          <View style={styles.lock}>
            <View style={styles.lockIcon}>
              <Icon name="lock-closed" size={18} color={colors.brand} />
            </View>
            <Text variant="bodyStrong" center>开通会员解锁全部预测</Text>
            <Text variant="caption" color={colors.muted} center>
              会员可查看全部 {total} 维预测与 {markets.length} 个市场
            </Text>
            <Button label="开通会员" size="sm" onPress={onUnlock} />
          </View>
        ) : null}
      </View>

      {!locked && markets.length ? (
        <View style={styles.marketGrid}>
          {markets.map((market) => (
            <View key={market.key} style={[styles.marketCard, { width: marketWidth }]}>
              <View style={styles.marketHead}>
                <Text variant="captionStrong" style={styles.flex} numberOfLines={1}>
                  {market.name}
                </Text>
                {market.line ? (
                  <Text variant="caption" color={colors.brand} mono>{market.line}</Text>
                ) : null}
              </View>
              {market.selections.map((row) => (
                <View key={`${market.key}-${row.label}`} style={styles.selectionRow}>
                  <Text variant="caption" color={colors.muted} style={styles.flex} numberOfLines={1}>
                    {row.label}
                  </Text>
                  <Text variant="captionStrong" mono>{row.price?.toFixed(2) ?? "—"}</Text>
                  <Text variant="caption" color={colors.subtle} style={styles.probability}>
                    {row.probability != null ? `${row.probability.toFixed(0)}%` : "—"}
                  </Text>
                </View>
              ))}
            </View>
          ))}
        </View>
      ) : null}

      {locked && total > preview.length ? (
        <Text variant="caption" color={colors.subtle}>
          还有 {total - preview.length} 维预测与市场已锁定
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.md, gap: spacing.md },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.sm },
  headText: { gap: 2 },
  flex: { flex: 1 },
  board: { position: "relative", borderRadius: radii.md, overflow: "hidden" },
  lockedBoard: { minHeight: 300 },
  rows: { gap: 0 },
  lockedRows: { opacity: 0.14 },
  dim: { paddingVertical: spacing.md, gap: 2 },
  dimLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  dimHead: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm, marginBottom: 2 },
  marketGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.sm },
  marketCard: {
    gap: 4,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  marketHead: { flexDirection: "row", alignItems: "baseline", gap: spacing.xs, marginBottom: 2 },
  selectionRow: { flexDirection: "row", alignItems: "baseline", gap: spacing.xs },
  probability: { width: 38, textAlign: "right" },
  lock: {
    position: "absolute",
    left: spacing.sm,
    right: spacing.sm,
    top: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radii.md,
    backgroundColor: colors.lockCover,
    borderWidth: 1,
    borderColor: colors.line,
  },
  lockIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
  },
});
