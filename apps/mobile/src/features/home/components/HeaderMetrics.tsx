import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { Text } from "@/components/ui";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { colors, spacing } from "@/theme/tokens";
import type { EngineStatus } from "@/features/home/queries";

/**
 * HeaderMetrics：不点击、不展开。
 * 只回答两件事：助理是否在线，今天读了多少数据。
 */
export function HeaderMetrics({ engine, dataPoints }: {
  engine: EngineStatus | null;
  dataPoints?: number;
}) {
  const reduced = useReducedMotion();
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (reduced) {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 0.35, duration: 900, useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [pulse, reduced]);

  if (!engine) {
    return (
      <View style={styles.metrics}>
        <Text variant="caption" color={colors.muted}>正在连接模型…</Text>
      </View>
    );
  }
  const points = Math.max(0, Math.round(dataPoints ?? engine.today_data_points ?? 0));
  const predictionTypes = Math.max(0, Math.round(engine.sportmonks_prediction_types ?? 0));
  const read = points >= 10000 ? `${(points / 10000).toFixed(1)}万` : String(points);
  return (
    <View style={styles.metrics} accessibilityLabel="AI 助理状态">
      <View style={styles.line}>
        <Animated.View style={[styles.dot, { opacity: pulse }]} />
        <Text variant="captionStrong" color={colors.brand} numberOfLines={1}>AI助理在线</Text>
      </View>
      <Text variant="caption" color={colors.muted} numberOfLines={1}>
        {points > 0 ? `已读${read}条` : "数据同步中"}
        {predictionTypes > 0 ? ` · ${predictionTypes}维预测` : ""}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  metrics: { alignItems: "flex-end", gap: 1, maxWidth: 190 },
  line: { flexDirection: "row", alignItems: "center", gap: spacing.xs, maxWidth: 190 },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.brandAccent,
    flexShrink: 0,
  },
});
