import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Icon, Text } from "@/components/ui";
import { formatTime } from "@/lib/format";
import type { LiveMatch, ResultMatch } from "../queries";
import { scoreStatusLabel, stateLabel } from "../labels";

function scoreText(value: number | null | undefined): string {
  return value == null ? "–" : String(value);
}

/** 即时行：只展示进行中的比分与阶段，不出现任何预测字段。 */
export function LiveMatchCard({
  match,
  onPress,
}: {
  match: LiveMatch;
  onPress: () => void;
}) {
  const minute = match.minute ? `${match.minute}'` : stateLabel(match.state);
  const hasHalf = match.ht_home != null && match.ht_away != null;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${match.home} 对 ${match.away}，${stateLabel(match.state)}，比分 ${scoreText(match.score_home)} 比 ${scoreText(match.score_away)}`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={[styles.minuteBox, isBreak(match.state) && styles.minuteBreak]}>
        <Text variant="h3" color={isBreak(match.state) ? colors.amber : colors.green}>
          {minute}
        </Text>
        <Text variant="caption" color={colors.muted} numberOfLines={1}>
          {stateLabel(match.state)}
        </Text>
      </View>
      <View style={styles.body}>
        <TeamRow name={match.home} score={match.score_home} />
        <TeamRow name={match.away} score={match.score_away} />
        <View style={styles.metaRow}>
          <Text variant="caption" color={colors.muted} numberOfLines={1}>
            {match.league || "未分类"}
            {match.match_no ? ` · ${match.match_no}` : ""}
            {hasHalf ? ` · 半场 ${match.ht_home}-${match.ht_away}` : ""}
          </Text>
        </View>
      </View>
      <Icon name="chevron-forward" size={16} color={colors.subtle} />
    </Pressable>
  );
}

/** 赛果行：FT90 口径，加时/点球单独标注。 */
export function ResultMatchCard({ match }: { match: ResultMatch }) {
  const hasHalf = match.ht_home != null && match.ht_away != null;
  return (
    <View style={styles.card}>
      <View style={styles.statusCol}>
        <Text variant="captionStrong" color={colors.green}>
          {scoreStatusLabel(match.status)}
        </Text>
        <Text variant="caption" color={colors.subtle}>{formatTime(match.kickoff)}</Text>
      </View>
      <View style={styles.body}>
        <TeamRow name={match.home} score={match.score_home} strong />
        <TeamRow name={match.away} score={match.score_away} strong />
        <View style={styles.metaRow}>
          <Text variant="caption" color={colors.muted} numberOfLines={1}>
            {match.league || "未分类"}
            {match.match_no ? ` · ${match.match_no}` : ""}
            {hasHalf ? ` · 半场 ${match.ht_home}-${match.ht_away}` : ""}
          </Text>
        </View>
      </View>
    </View>
  );
}

function TeamRow({
  name,
  score,
  strong = false,
}: {
  name: string;
  score: number | null | undefined;
  strong?: boolean;
}) {
  return (
    <View style={styles.teamRow}>
      <Text variant={strong ? "bodyStrong" : "body"} numberOfLines={1} style={styles.teamName}>
        {name || "待同步"}
      </Text>
      <Text variant="h3" style={styles.teamScore}>
        {scoreText(score)}
      </Text>
    </View>
  );
}

function isBreak(state: string): boolean {
  return state.toUpperCase() === "HT";
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.line,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.md,
    minHeight: 92,
  },
  pressed: { opacity: 0.72 },
  minuteBox: {
    width: 60,
    alignSelf: "stretch",
    borderRadius: radii.md,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
    gap: 1,
  },
  minuteBreak: { backgroundColor: colors.amberSoft },
  statusCol: { width: 52, alignItems: "center", gap: 2 },
  body: { flex: 1, gap: 4 },
  teamRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  teamName: { flex: 1 },
  teamScore: { minWidth: 22, textAlign: "right", fontVariant: ["tabular-nums"] },
  metaRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
});
