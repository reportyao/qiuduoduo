import { StyleSheet, View } from "react-native";
import type { SportmonksMarketBoard, SportmonksPredictionHighlight } from "@/domain/types";
import { Button, Icon, Text } from "@/components/ui";
import { ageLabel } from "@/lib/freshness";
import { colors, radii, spacing } from "@/theme/tokens";
import { predictionValue } from "./SportmonksIntelSection";

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
  if (!predictions.length && !markets.length) return null;
  const preview = locked ? predictions.slice(0, 6) : predictions;
  const shownMarkets = locked ? markets.slice(0, 1) : markets;
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

      <View style={styles.board}>
        <View style={[styles.rows, locked && styles.lockedRows]} pointerEvents="none">
          {preview.map((item) => (
            <View key={item.key} style={styles.row}>
              <Text variant="small" color={colors.muted} style={styles.label} numberOfLines={2}>
                {item.label}
              </Text>
              <Text variant="smallStrong" style={styles.value} numberOfLines={2}>
                {predictionValue(item)}
              </Text>
            </View>
          ))}
          {shownMarkets.map((market) => (
            <View key={market.key} style={styles.row}>
              <Text variant="small" color={colors.muted} style={styles.label} numberOfLines={2}>
                {market.name}{market.line ? ` ${market.line}` : ""}
              </Text>
              <Text variant="smallStrong" style={styles.value} numberOfLines={2}>
                {market.selections.map((row) =>
                  `${row.label} ${row.price ?? "—"}（${row.probability ?? "—"}%）`).join(" · ")}
              </Text>
            </View>
          ))}
        </View>

        {locked ? (
          <View style={styles.lock}>
            <View style={styles.lockIcon}>
              <Icon name="lock-closed" size={18} color={colors.green} />
            </View>
            <Text variant="bodyStrong" center>开通会员解锁全部预测</Text>
            <Text variant="caption" color={colors.muted} center>
              会员可查看全部 {total} 维预测与 {markets.length} 个市场
            </Text>
            <Button label="开通会员" size="sm" onPress={onUnlock} />
          </View>
        ) : null}
      </View>

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
  board: { position: "relative", borderRadius: radii.md, overflow: "hidden" },
  rows: { gap: 1 },
  lockedRows: { opacity: 0.16 },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    paddingVertical: 7,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  label: { width: 108, lineHeight: 18 },
  value: { flex: 1, lineHeight: 19 },
  lock: {
    position: "absolute",
    left: spacing.sm,
    right: spacing.sm,
    top: "12%",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radii.md,
    backgroundColor: "rgba(255,255,255,0.94)",
    borderWidth: 1,
    borderColor: colors.line,
  },
  lockIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
  },
});
