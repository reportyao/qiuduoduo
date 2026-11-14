import { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import type { components } from "@jieqiu/api-client";
import { colors, radii, spacing } from "@/theme/tokens";
import { Card, Chip, Text } from "@/components/ui";
import { pct } from "@/lib/format";
import { usePerformanceQuery } from "../queries";

type Performance = components["schemas"]["PerformanceResponse"];

function rateColor(rate: number | null | undefined): string {
  if (rate == null) return colors.muted;
  if (rate >= 0.55) return colors.green;
  if (rate >= 0.45) return colors.amber;
  return colors.danger;
}

/** 横向条形行：名称 + 条 + 右侧数值。 */
function BarRow({
  label,
  value,
  maxValue,
  note,
  tone,
}: {
  label: string;
  value: number;
  maxValue: number;
  note: string;
  tone: string;
}) {
  const width = maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 2;
  return (
    <View style={styles.barRow}>
      <Text variant="small" color={colors.muted} style={styles.barLabel} numberOfLines={1}>
        {label}
      </Text>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${width}%`, backgroundColor: tone }]} />
      </View>
      <Text variant="captionStrong" mono style={styles.barValue}>{note}</Text>
    </View>
  );
}

/**
 * 战绩看板：趋势 / 按市场 / 校准。
 * 全部用 RN View 画条，不引第三方图表库。
 */
export function PerformanceDashboard({ days = 30 }: { days?: number }) {
  const query = usePerformanceQuery(days, true);
  const data = query.data as Performance | undefined;

  const trend = useMemo(() => data?.trend?.filter((p) => p.settled > 0) ?? [], [data]);
  const maxTrendSettled = useMemo(
    () => Math.max(...trend.map((p) => p.settled), 1),
    [trend],
  );
  const maxMarketSettled = useMemo(
    () => Math.max(...(data?.by_market ?? []).map((row) => row.settled), 1),
    [data],
  );

  if (query.isLoading) {
    return (
      <Card style={styles.card}>
        <Text variant="small" color={colors.muted}>战绩看板加载中…</Text>
      </Card>
    );
  }
  if (query.isError || !data || data.total_settled === 0) {
    return null; // 无数据时不渲染，空态由列表兜底
  }

  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="overline" color={colors.green}>战绩看板</Text>
          <Text variant="h3">近 {data.days} 天</Text>
        </View>
        <View style={styles.kpi}>
          <Text variant="h2" color={rateColor(data.hit_rate)}>{pct(data.hit_rate, 1)}</Text>
          <Text variant="caption" color={colors.muted}>
            {data.total_hits}/{data.total_settled} 命中
          </Text>
        </View>
      </View>

      {trend.length >= 2 ? (
        <View style={styles.section}>
          <Text variant="captionStrong" color={colors.muted}>每日命中率</Text>
          <View style={styles.trendList}>
            {trend.slice(-10).map((point) => (
              <BarRow
                key={point.date}
                label={point.date.slice(5)}
                value={point.settled}
                maxValue={maxTrendSettled}
                note={point.rate != null ? `${pct(point.rate, 0)} · ${point.settled} 项` : `${point.settled} 项`}
                tone={rateColor(point.rate)}
              />
            ))}
          </View>
        </View>
      ) : null}

      {(data?.by_market ?? []).length ? (
        <View style={styles.section}>
          <Text variant="captionStrong" color={colors.muted}>按市场拆分</Text>
          <View style={styles.trendList}>
            {data?.by_market?.map((row) => (
              <BarRow
                key={row.market}
                label={row.market}
                value={row.settled}
                maxValue={maxMarketSettled}
                note={`${pct(row.rate, 0)} · ${row.hits}/${row.settled}`}
                tone={rateColor(row.rate)}
              />
            ))}
          </View>
        </View>
      ) : null}

      {(data?.calibration ?? []).length >= 2 ? (
        <View style={styles.section}>
          <View style={styles.calibrationHead}>
            <Text variant="captionStrong" color={colors.muted}>校准曲线</Text>
            <Chip label="预测 vs 实际" tone="neutral" />
          </View>
          <View style={styles.calibrationList}>
            {data?.calibration?.map((bucket) => {
              const gap = bucket.actual != null
                ? (bucket.actual - bucket.predicted) * 100 : null;
              const tone = gap == null ? colors.muted
                : gap >= -5 ? colors.green : gap <= -15 ? colors.danger : colors.amber;
              return (
                <View key={bucket.bucket} style={styles.calibrationRow}>
                  <Text variant="captionStrong" mono>{bucket.bucket}</Text>
                  <Text variant="caption" color={colors.muted}>
                    预测 {pct(bucket.predicted, 0)}
                  </Text>
                  <Text variant="captionStrong" color={tone} mono>
                    实际 {bucket.actual != null ? pct(bucket.actual, 0) : "—"}
                  </Text>
                  <Text variant="caption" color={colors.subtle}>
                    {bucket.count} 项
                  </Text>
                </View>
              );
            })}
          </View>
          <Text variant="caption" color={colors.subtle} style={styles.note}>
            实际 ≥ 预测说明模型偏保守；差距超过 15pp 用红色标出。
          </Text>
        </View>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: spacing.lg, marginTop: spacing.md },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  flex: { flex: 1, gap: 2 },
  kpi: { alignItems: "flex-end", gap: 1 },
  section: { gap: spacing.sm },
  trendList: { gap: spacing.xs },
  barRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  barLabel: { width: 42, fontVariant: ["tabular-nums"] },
  track: {
    flex: 1,
    height: 14,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceSunken,
    overflow: "hidden",
  },
  fill: { height: "100%", borderRadius: radii.pill },
  barValue: { width: 82, textAlign: "right", color: colors.ink },
  calibrationHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  calibrationList: { gap: spacing.xs },
  calibrationRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  note: { lineHeight: 16 },
});
