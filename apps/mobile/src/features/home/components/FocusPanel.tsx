import { StyleSheet, View } from "react-native";
import type { MatchFocus } from "@/domain/focusAdapters";
import { colors, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

const REASON: Record<string, string> = {
  login_required: "登录后可记注",
  settled: "这场已结算",
  sale_closed: "已停售",
  already_bet: "已经记过一注",
  rested: "休息中，今晚先不下注",
  self_excluded: "自排除生效中",
  under18: "未满 18 周岁，仅可查看公开账本",
};

export function FocusPanel({
  focus,
  loading,
}: {
  focus: MatchFocus | null | undefined;
  loading: boolean;
}) {
  if (loading && !focus) {
    return (
      <View style={styles.panel}>
        <Text variant="caption" color={colors.subtle}>正在核对数据覆盖…</Text>
      </View>
    );
  }
  if (!focus) return null;
  const betAction = focus.actions.find((action) => action.id === "bet");
  const facts = focus.facts.slice(0, 3);
  return (
    <View style={styles.panel}>
      <View style={styles.head}>
        <Text variant="overline" color={colors.green}>
          数据覆盖 {focus.coverage.score}
        </Text>
        <Text variant="caption" color={focus.coverage.deepEligible ? colors.green : colors.amber}>
          {focus.coverage.deepEligible ? "可深读" : "仅轻读"}
        </Text>
      </View>
      {focus.coverage.missing.length ? (
        <Text variant="caption" color={colors.subtle}>
          缺：{focus.coverage.missing.join(" / ")}
        </Text>
      ) : null}
      {facts.map((fact) => (
        <View key={fact.id} style={styles.factRow}>
          <Text variant="captionStrong" color={colors.ink}>{fact.label}</Text>
          <Text variant="caption" color={colors.muted} style={styles.factValue} numberOfLines={2}>
            {fact.value}
          </Text>
        </View>
      ))}
      {focus.unknowns.slice(0, 2).map((item) => (
        <Text key={item} variant="caption" color={colors.subtle}>
          · 未确认：{item}
        </Text>
      ))}
      {betAction && !betAction.enabled && betAction.reason ? (
        <Text variant="caption" color={colors.amber} style={styles.reason}>
          {REASON[betAction.reason] ?? betAction.reason}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    marginTop: spacing.sm,
    padding: spacing.base,
    borderRadius: 12,
    backgroundColor: colors.bgElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    gap: 5,
  },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  factRow: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  factValue: { flex: 1 },
  reason: { marginTop: 2 },
});
