import { StyleSheet, View } from "react-native";
import type { ProbabilityTriple } from "@/domain/types";
import { pct } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

const SEGMENTS = [
  { key: "home" as const, label: "主胜", color: colors.green },
  { key: "draw" as const, label: "平", color: colors.amber },
  { key: "away" as const, label: "客胜", color: colors.subtle },
];

export function ProbabilityBar({
  probs,
  dark = false,
  label = "市场去水概率",
}: {
  probs: ProbabilityTriple;
  dark?: boolean;
  label?: string;
}) {
  const total = probs.home + probs.draw + probs.away || 1;
  return (
    <View style={styles.wrap}>
      <View style={styles.legend}>
        {SEGMENTS.map((segment) => (
          <View key={segment.key} style={styles.legendItem}>
            <View style={[styles.swatch, { backgroundColor: segment.color }]} />
            <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
              {segment.label} {pct(probs[segment.key] / total)}
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
              backgroundColor: segment.color,
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
  trackDark: { backgroundColor: "rgba(255,255,255,0.10)" },
});
