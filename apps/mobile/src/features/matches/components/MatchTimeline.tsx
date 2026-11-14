import { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import type { components } from "@jieqiu/api-client";
import { Card, Icon, Text } from "@/components/ui";
import { colors, radii, spacing } from "@/theme/tokens";

type Postmatch = components["schemas"]["PostmatchData"];
type HalfCheck = components["schemas"]["HalfCheck"];

function minuteLabel(minute: number | null | undefined): string {
  return minute != null ? `${minute}'` : "—";
}

/**
 * 时间轴复盘：进球按分钟排列，半场位置插入「赛前预测 vs 实际半场」对照。
 * 数据来自 Sportmonks 赛后 events 与赛前快照的半场胜平负 argmax。
 */
export function MatchTimeline({
  postmatch,
  halfCheck,
  scoreHome,
  scoreAway,
}: {
  postmatch: Postmatch | null;
  halfCheck: HalfCheck | null;
  scoreHome: number | null;
  scoreAway: number | null;
}) {
  const goals = useMemo(
    () =>
      [...(postmatch?.goals ?? [])].sort(
        (a, b) => (a.minute ?? 999) - (b.minute ?? 999),
      ),
    [postmatch],
  );
  const scoredGoals = useMemo(() => {
    let home = 0;
    let away = 0;
    return goals.map((goal) => {
      if (goal.side === "home") home++;
      else if (goal.side === "away") away++;
      return { ...goal, cumulative: `${home}-${away}` };
    });
  }, [goals]);
  const hasHalf = halfCheck != null && halfCheck.predicted_ht !== "";
  if (!postmatch && !hasHalf) return null;
  const firstSecondHalf = scoredGoals.findIndex((goal) => (goal.minute ?? 0) > 45);
  const rendered = scoredGoals.map((goal, index) => {
    const cumulative = goal.cumulative;
    const halfBefore = hasHalf && index === firstSecondHalf;
    const isLast = index === scoredGoals.length - 1;
    return (
      <View key={`${goal.minute}-${goal.player}-${index}`} style={styles.event}>
        <View style={styles.marker}>
          <View style={styles.dot} />
          {!isLast || halfBefore ? <View style={styles.line} /> : null}
          {halfBefore ? <View style={[styles.line, styles.lineHalf]} /> : null}
        </View>
        <View style={styles.eventBody}>
          <Text variant="captionStrong" mono>
            {minuteLabel(goal.minute)} {cumulative}
          </Text>
          <View style={styles.playerRow}>
            <Icon name="football" size={14} color={colors.muted} />
            <Text variant="small" color={colors.muted} numberOfLines={1} style={styles.flex}>
              {goal.player || "进球"}
              {goal.side === "home" ? "（主）" : goal.side === "away" ? "（客）" : ""}
            </Text>
          </View>
        </View>
      </View>
    );
  });
  if (hasHalf && (firstSecondHalf <= 0 || scoredGoals.length === 0)) {
    rendered.unshift(
      <View key="half-marker" style={styles.event}>
        <View style={styles.marker}>
          <View style={styles.dotHalf} />
          <View style={styles.line} />
        </View>
        <View style={styles.eventBody}>
          <Text variant="captionStrong" mono>45'</Text>
          <HalfCheckRow check={halfCheck!} />
        </View>
      </View>,
    );
  }

  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="overline" color={colors.brand}>时间轴复盘</Text>
          <Text variant="h3">
            {postmatch?.score_home ?? scoreHome ?? "—"} -{" "}
            {postmatch?.score_away ?? scoreAway ?? "—"}
          </Text>
        </View>
        {postmatch?.xg_home != null || postmatch?.xg_away != null ? (
          <Text variant="caption" color={colors.subtle} style={styles.xg}>
            xG {postmatch?.xg_home ?? "—"} / {postmatch?.xg_away ?? "—"}
          </Text>
        ) : null}
      </View>

      {rendered.length ? rendered : (
        <Text variant="small" color={colors.muted}>这场没有进球事件记录。</Text>
      )}

      {postmatch?.captured_at ? (
        <Text variant="caption" color={colors.subtle} style={styles.note}>
          时间线来自 Sportmonks 赛后事件；半场对照来自赛前快照。
        </Text>
      ) : null}
    </Card>
  );
}

function HalfCheckRow({ check }: { check: HalfCheck }) {
  return (
    <View style={[styles.halfBox, check.on_track && styles.halfBoxOk]}>
      <Text variant="caption" color={colors.muted}>半场对照</Text>
      <Text variant="smallStrong" color={check.on_track ? colors.brand : colors.amber}>
        预测 {check.predicted_ht} / 实际 {check.actual_ht}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: spacing.md },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  flex: { flex: 1, gap: 1 },
  xg: { fontVariant: ["tabular-nums"] },
  event: { flexDirection: "row", gap: spacing.md },
  marker: { width: 20, alignItems: "center" },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.brand,
    marginTop: 4,
  },
  dotHalf: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: colors.amber,
    backgroundColor: colors.surface,
    marginTop: 4,
  },
  line: { width: 2, flex: 1, backgroundColor: colors.line, marginTop: 2 },
  lineHalf: { backgroundColor: colors.amberLine },
  eventBody: { flex: 1, gap: 2, paddingBottom: spacing.md },
  playerRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  halfBox: {
    marginTop: 3,
    padding: spacing.sm,
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceSunken,
    gap: 2,
  },
  halfBoxOk: { backgroundColor: colors.brandSoft },
  note: { marginTop: spacing.xs, lineHeight: 16 },
});
