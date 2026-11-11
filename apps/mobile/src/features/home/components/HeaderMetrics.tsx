import { StyleSheet, View } from "react-native";
import { StatusDot, Text } from "@/components/ui";
import { relativeTime } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

/** 首页顶栏右侧的在线与数据点状态。 */
export function HeaderMetrics({
  stream,
  pulse,
  now,
}: {
  stream: { generatedAt?: string | null } | null;
  pulse: { display: { dataPoints: number }; asOf?: string | null } | null | undefined;
  now: number;
}) {
  const points = pulse?.display.dataPoints ?? 0;
  return (
    <View style={styles.metrics}>
      <View style={styles.metricTop}>
        <StatusDot color={colors.greenAccent} />
        <Text variant="caption" color={colors.muted}>在线</Text>
      </View>
      <Text variant="captionStrong" color={colors.green}>
        预测引擎 v3 · {points > 0 ? `${points} 个数据点` : "等待同步"}
      </Text>
      <Text variant="caption" color={colors.subtle}>
        {pulse?.asOf
          ? relativeTime(pulse.asOf, now)
          : stream?.generatedAt
            ? relativeTime(stream.generatedAt, now)
            : "实时"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  metrics: { alignItems: "flex-end", gap: 1 },
  metricTop: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
});
