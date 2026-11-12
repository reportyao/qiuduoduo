import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { Text } from "@/components/ui";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { colors, spacing } from "@/theme/tokens";
import type { EngineStatus } from "@/features/home/queries";

/**
 * HeaderMetrics：不点击、不展开。
 * 主文案保留“预测引擎 + 数据点”，并增加陪伴时长与盘口/模型监控。
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
        <Text variant="caption" color={colors.muted}>正在连接预测引擎…</Text>
      </View>
    );
  }
  const points = Math.max(0, Math.round(dataPoints ?? engine.today_data_points ?? 0));
  const predictionTypes = Math.max(0, Math.round(engine.sportmonks_prediction_types ?? 0));
  const lineups = Math.max(0, Math.round(engine.sportmonks_lineups ?? 0));
  return (
    <View style={styles.metrics} accessibilityLabel="预测引擎状态">
      <Text variant="caption" color={colors.muted} numberOfLines={1}>
        已为你稳定运行 {engine.uptime_hours ?? "—"} 小时
      </Text>
      <Text variant="captionStrong" color={colors.green} numberOfLines={1}>
        预测引擎 {engine.version}
      </Text>
      <Text variant="caption" color={colors.muted} numberOfLines={1}>
        {points > 0 ? `今日采集 ${points.toLocaleString()} 条数据点` : "今日数据同步中"}
      </Text>
      <View style={styles.line}>
        <Animated.View style={[styles.dot, { opacity: pulse }]} />
        <Text variant="caption" color={colors.muted} numberOfLines={1}>
          {predictionTypes > 0
            ? `${engine.markets_monitored} 盘口 · ${predictionTypes} 预测`
            : `${engine.markets_monitored} 盘口配置 · ${engine.models_reviewing} 模型位`}
          {lineups > 0 ? ` · ${lineups} 场首发` : ""}
        </Text>
      </View>
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
    backgroundColor: colors.green,
    flexShrink: 0,
  },
});
