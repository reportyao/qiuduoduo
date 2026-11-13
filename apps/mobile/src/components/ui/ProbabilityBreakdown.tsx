import { StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "./Text";

export interface ProbabilityDatum {
  key: string;
  label: string;
  value: number;
}

interface ProbabilityBreakdownProps {
  items: ProbabilityDatum[];
  /** 0-100 传 percent，0-1 传 ratio。 */
  unit?: "percent" | "ratio";
  predictedKey?: string;
  actualKey?: string;
  /** 只留前 N 项，其余收进“其他”；默认全部展示。 */
  maxItems?: number;
  dark?: boolean;
}

/**
 * 概率分布的统一表达：
 * 少量结果用一条堆叠条 + 图例；正确比分这种多结果用网格。
 * 预测项用绿色，实际结果用琥珀色描边，避免把 19 个比分堆成一段文字。
 */
export function ProbabilityBreakdown({
  items,
  unit = "percent",
  predictedKey,
  actualKey,
  maxItems,
  dark = false,
}: ProbabilityBreakdownProps) {
  const source = (maxItems && items.length > maxItems ? items.slice(0, maxItems) : items)
    .map((item) => ({ ...item, value: unit === "ratio" ? item.value * 100 : item.value }))
    .filter((item) => Number.isFinite(item.value) && item.value > 0);
  if (source.length === 0) return null;
  const total = source.reduce((sum, item) => sum + item.value, 0) || 1;
  const grid = source.length > 4;
  return (
    <View style={styles.wrap}>
      {!grid ? (
        <View style={[styles.track, dark && styles.trackDark]}>
          {source.map((item) => (
            <View
              key={item.key}
              style={{
                flex: Math.max(item.value / total, 0.015),
                backgroundColor: segmentColor(item.key, predictedKey, actualKey, dark),
              }}
            />
          ))}
        </View>
      ) : null}
      <View style={grid ? styles.grid : styles.legend}>
        {source.map((item) => {
          const predicted = item.key === predictedKey;
          const actual = item.key === actualKey;
          return (
            <View
              key={item.key}
              style={[
                grid ? styles.cell : styles.legendItem,
                predicted && (dark ? styles.cellPredictedDark : styles.cellPredicted),
                actual && !predicted && styles.cellActual,
              ]}
            >
              <View style={styles.cellText}>
                <Text
                  variant={grid ? "captionStrong" : "caption"}
                  color={predicted ? (dark ? colors.greenAccent : colors.green)
                    : actual ? colors.amber : (dark ? colors.mutedInverse : colors.muted)}
                  numberOfLines={1}
                  style={styles.flex}
                >
                  {item.label}
                </Text>
                <Text
                  variant={grid ? "captionStrong" : "captionStrong"}
                  mono
                  color={predicted ? (dark ? colors.greenAccent : colors.green)
                    : actual ? colors.amber : (dark ? colors.inkInverse : colors.ink)}
                >
                  {formatPct(item.value)}
                </Text>
              </View>
              {grid ? (
                <View style={[styles.miniTrack, dark && styles.miniTrackDark]}>
                  <View
                    style={[styles.miniFill, {
                      width: `${Math.max(2, (item.value / total) * 100)}%`,
                      backgroundColor: segmentColor(item.key, predictedKey, actualKey, dark),
                    }]}
                  />
                </View>
              ) : null}
            </View>
          );
        })}
      </View>
    </View>
  );
}

function formatPct(value: number): string {
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)}%`;
}

function segmentColor(key: string, predicted?: string, actual?: string, dark = false): string {
  if (key === predicted) return dark ? colors.greenAccent : colors.green;
  if (key === actual) return colors.amber;
  return dark ? "rgba(255,255,255,0.22)" : colors.lineStrong;
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, marginTop: spacing.xs },
  track: {
    flexDirection: "row",
    height: 9,
    borderRadius: radii.pill,
    overflow: "hidden",
    backgroundColor: colors.surfaceSunken,
  },
  trackDark: { backgroundColor: "rgba(255,255,255,0.12)" },
  legend: { flexDirection: "row", flexWrap: "wrap", columnGap: spacing.lg, rowGap: spacing.xs },
  legendItem: { flexDirection: "row", alignItems: "center" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  cell: {
    width: "31.8%",
    minHeight: 48,
    justifyContent: "center",
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceSunken,
  },
  cellPredicted: { backgroundColor: colors.greenSoft },
  cellPredictedDark: { backgroundColor: "rgba(168,228,201,0.14)" },
  cellActual: { borderWidth: 1, borderColor: colors.amberLine },
  cellText: { flexDirection: "row", alignItems: "baseline", gap: 3 },
  flex: { flex: 1 },
  miniTrack: { height: 3, borderRadius: radii.pill, backgroundColor: colors.line, overflow: "hidden" },
  miniTrackDark: { backgroundColor: "rgba(255,255,255,0.15)" },
  miniFill: { height: "100%", borderRadius: radii.pill },
});
