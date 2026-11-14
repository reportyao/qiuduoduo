import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Chip, Icon, Text } from "@/components/ui";
import { formatTime, pct } from "@/lib/format";
import type { PredictionAccuracy, PredictionHistoryMatch } from "../queries";
import { resultLabel, resultTone } from "../labels";

function mainPickText(main: PredictionHistoryMatch["main_prediction"]): string {
  if (!main) return "暂无主预测";
  if (main.direction) return main.direction;
  const key = main.key;
  const outcome: Record<string, string> = { home: "主胜", draw: "平局", away: "客胜" };
  if (outcome[key]) return outcome[key];
  if (key === "yes") return "大";
  if (key === "no") return "小";
  return key || main.label || "暂无主预测";
}

/** 命中率总览：唯一分母是 counted 的预测条目，不按比赛场次。 */
export function AccuracyCard({ summary }: { summary: PredictionAccuracy }) {
  const rate = summary.hit_rate;
  return (
    <View style={styles.hero}>
      <View style={styles.heroTop}>
        <View style={styles.heroRate}>
          <Text variant="overline" color={colors.greenAccent}>预测战绩</Text>
          <Text variant="metric" color={colors.white}>{pct(rate, 1)}</Text>
          <Text variant="small" color={colors.mutedInverse}>主流玩法命中率</Text>
        </View>
        <Text variant="caption" color={colors.mutedInverse}>
          已结算 {summary.settled_items} 条
        </Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${Math.round((rate ?? 0) * 100)}%` }]} />
      </View>
      <View style={styles.heroStats}>
        <Count label="命中" value={summary.hit_items} tone={colors.greenAccent} />
        <Count label="未中" value={summary.miss_items} tone={colors.inkInverse} />
        <Count label="走水" value={summary.push_items} tone={colors.mutedInverse} />
      </View>
      <Text variant="caption" color={colors.mutedInverse} style={styles.heroNote}>
        按预测条目统计 · 仅含有赛前快照的场次，角球、半全场只做对照。
      </Text>
    </View>
  );
}

function Count({
  label,
  value,
  tone = colors.inkInverse,
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <View style={styles.count}>
      <Text variant="bodyStrong" color={tone}>{value}</Text>
      <Text variant="caption" color={colors.mutedInverse}>{label}</Text>
    </View>
  );
}

/** 单场主预测卡：点开看 25 维预测 vs 实际。 */
export function PredictionMatchCard({
  match,
  onPress,
}: {
  match: PredictionHistoryMatch;
  onPress: () => void;
}) {
  const main = match.main_prediction;
  const pick = mainPickText(main);
  const result = main?.result ?? "insufficient_data";
  const score = match.score_home == null || match.score_away == null
    ? "待赛果"
    : `${match.score_home} - ${match.score_away}`;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${match.home} 对 ${match.away}，主预测 ${pick}，${resultLabel(result)}`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.cardTop}>
        <Text variant="caption" color={colors.muted} numberOfLines={1} style={styles.flex}>
          {match.league || "未分类"}
          {match.match_no ? ` · ${match.match_no}` : ""}
          {match.kickoff ? ` · ${formatTime(match.kickoff)}` : ""}
        </Text>
        <Chip label={resultLabel(result)} tone={resultTone(result)} />
      </View>
      <View style={styles.teams}>
        <View style={styles.flex}>
          <Text variant="bodyStrong" numberOfLines={1}>{match.home}</Text>
          <Text variant="bodyStrong" numberOfLines={1}>{match.away}</Text>
        </View>
        <Text variant="h3" color={colors.ink} style={styles.score}>{score}</Text>
      </View>
      <View style={styles.pickRow}>
        <View style={styles.flex}>
          <Text variant="caption" color={colors.muted}>主预测</Text>
          <Text variant="h3" color={result === "hit" ? colors.green : colors.ink} numberOfLines={1}>
            {pick}
          </Text>
        </View>
        <View style={styles.probability}>
          <Text variant="caption" color={colors.muted}>预测概率</Text>
          <Text variant="bodyStrong" mono>
            {main?.probability != null ? pct(main.probability, 1) : "—"}
          </Text>
        </View>
      </View>
      <View style={styles.cardFooter}>
        <Text variant="caption" color={colors.muted} style={styles.flex}>
          实际 {main?.actual || "待结算"} · 已结算 {match.settled_dimensions}/{match.total_dimensions} 项
        </Text>
        <Icon name="chevron-forward" size={18} color={colors.subtle} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hero: {
    backgroundColor: colors.heroBottom,
    borderRadius: radii.hero,
    padding: spacing.x4,
    marginTop: spacing.md,
    gap: spacing.lg,
  },
  heroTop: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: spacing.md },
  heroRate: { gap: 1, flex: 1 },
  heroStats: { flexDirection: "row", gap: spacing.x6 },
  count: { gap: 1 },
  track: {
    height: 5,
    borderRadius: radii.pill,
    backgroundColor: colors.whiteOverlay12,
    overflow: "hidden",
  },
  fill: { height: "100%", borderRadius: radii.pill, backgroundColor: colors.greenAccent },
  heroNote: { lineHeight: 16 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.lg,
    marginTop: spacing.md,
    gap: spacing.md,
  },
  pressed: { opacity: 0.72 },
  cardTop: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  flex: { flex: 1 },
  teams: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  score: { minWidth: 52, textAlign: "right", fontVariant: ["tabular-nums"] },
  pickRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    paddingTop: spacing.md,
  },
  probability: { alignItems: "flex-end", gap: 1 },
  cardFooter: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
});
