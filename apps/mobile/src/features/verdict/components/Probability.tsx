import { StyleSheet, View } from "react-native";
import type { ProbabilityTriple } from "@/domain/types";
import { pct } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

const SEGMENTS = [
  { key: "home" as const, label: "主胜" },
  { key: "draw" as const, label: "平" },
  { key: "away" as const, label: "客胜" },
];

function segmentColor(key: "home" | "draw" | "away", dark: boolean): string {
  if (key === "home") return dark ? colors.brandAccent : colors.brand;
  if (key === "draw") return colors.amber;
  return dark ? colors.mutedInverse : colors.muted;
}

export function ProbabilityBar({
  probs,
  dark = false,
  label = "市场去水概率",
  pool,
}: {
  probs: ProbabilityTriple;
  dark?: boolean;
  label?: string;
  /** 让球盘要标明概率属于让球后的主/平/客，不能直接写主胜。 */
  pool?: string;
}) {
  const total = probs.home + probs.draw + probs.away || 1;
  const prefix = pool === "hhad" ? "让球" : "";
  return (
    <View style={styles.wrap}>
      <View style={styles.legend}>
        {SEGMENTS.map((segment) => (
          <View key={segment.key} style={styles.legendItem}>
            <View style={[styles.swatch, { backgroundColor: segmentColor(segment.key, dark) }]} />
            <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
              {prefix}{segment.label} {pct(probs[segment.key] / total)}
            </Text>
          </View>
        ))}
      </View>
      <View style={[styles.track, dark && styles.trackDark]}>
        {SEGMENTS.map((segment) => (
          <View
            key={segment.key}
            style={{
              flex: Math.max(probs[segment.key] / total, 0.01),
              backgroundColor: segmentColor(segment.key, dark),
            }}
          />
        ))}
      </View>
      <Text variant="caption" color={dark ? colors.mutedInverse : colors.subtle}>
        {label} · 三项相加为 100%，已剔除抽水
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.xs },
  legend: { flexDirection: "row", flexWrap: "wrap", gap: spacing.base },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  swatch: { width: 6, height: 6, borderRadius: 3 },
  track: {
    flexDirection: "row",
    height: 7,
    borderRadius: radii.pill,
    overflow: "hidden",
    backgroundColor: colors.surfaceSunken,
  },
  trackDark: { backgroundColor: colors.whiteOverlay10 },
});
