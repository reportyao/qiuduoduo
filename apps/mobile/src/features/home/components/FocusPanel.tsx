import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { MatchFocus } from "@/domain/focusAdapters";
import { coverageGaps } from "@/features/home/focusCoverage";
import { colors, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

const clean = (text: string) => text.replace(/Sportmonks/g, "球多多自研AI引擎预测");

const REASON: Record<string, string> = {
  login_required: "登录后可记注",
  settled: "这场已结算",
  sale_closed: "已停售",
  already_bet: "已经记过一注",
  rested: "休息中，今晚先不下注",
  self_excluded: "自排除生效中",
  under18: "未满 18 周岁，仅可查看公开账本",
};

/** 聚焦卡：默认露出核心三关 + 2 条情报，可展开全部事实。 */
export function FocusPanel({
  focus,
  loading,
}: {
  focus: MatchFocus | null | undefined;
  loading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  if (loading && !focus) {
    return (
      <View style={styles.panel}>
        <Text variant="caption" color={colors.subtle}>正在核对数据覆盖…</Text>
      </View>
    );
  }
  if (!focus) return null;
  const betAction = focus.actions.find((action) => action.id === "bet");
  const coreKinds = new Set(["price", "market", "model"]);
  const priority: Record<string, number> = {
    lineup: 0, standing: 1, injury: 2, h2h: 3,
    form: 4, venue: 5, weather: 6, referee: 7, coach: 8, prediction: 9,
  };
  const core = focus.facts.filter((fact) => coreKinds.has(fact.kind)).slice(0, 3);
  const intel = focus.facts
    .filter((fact) => !coreKinds.has(fact.kind))
    .sort((a, b) => (priority[a.kind] ?? 20) - (priority[b.kind] ?? 20));
  const visible = expanded ? focus.facts : [...core, ...intel.slice(0, 2)];
  const hidden = Math.max(0, focus.facts.length - visible.length);
  const unknownVisible = expanded ? focus.unknowns : focus.unknowns.slice(0, 2);
  const gaps = coverageGaps(focus.coverage);
  const sm = focus.sportmonks;
  const homeLine = sm?.lineups?.home;
  const awayLine = sm?.lineups?.away;
  const hasLineups = Boolean(homeLine?.starters?.length && awayLine?.starters?.length);
  return (
    <View style={styles.panel}>
      <View style={styles.head}>
        <Text variant="overline" color={colors.green}>
          数据覆盖 {focus.coverage.score}
        </Text>
        <View style={styles.headRight}>
          {sm ? <Text variant="caption" color={colors.green}>球多多自研AI引擎预测</Text> : null}
          <Text variant="caption" color={focus.coverage.deepEligible ? colors.green : colors.amber}>
            {focus.coverage.deepEligible ? "可深读" : "仅轻读"}
          </Text>
        </View>
      </View>
      {gaps.stale.length ? (
        <Text variant="caption" color={colors.subtle}>
          偏旧：{gaps.stale.join(" / ")}
        </Text>
      ) : null}
      {gaps.missing.length ? (
        <Text variant="caption" color={colors.subtle}>
          缺：{gaps.missing.join(" / ")}
        </Text>
      ) : null}
      {visible.map((fact) => (
        <View key={fact.id} style={styles.factRow}>
          <Text variant="captionStrong" color={colors.ink}>{clean(fact.label)}</Text>
          <View style={styles.factBody}>
            <Text variant="caption" color={colors.muted} numberOfLines={expanded ? 4 : 2}>
              {clean(fact.value)}
            </Text>
            {expanded && fact.detail ? (
              <Text variant="caption" color={colors.subtle} numberOfLines={3}>
                {clean(fact.detail)}
              </Text>
            ) : null}
          </View>
        </View>
      ))}
      {hasLineups && homeLine && awayLine ? (
        <Text variant="caption" color={colors.subtle} numberOfLines={1}>
          首发已同步 · {homeLine.formation || "—"} / {awayLine.formation || "—"}
          {sm?.sidelined?.length ? ` · 伤停 ${sm.sidelined.length} 人` : ""}
        </Text>
      ) : null}
      {hidden > 0 ? (
        <Pressable
          onPress={() => setExpanded(true)}
          accessibilityRole="button"
          accessibilityLabel={`展开全部 ${focus.facts.length} 条情报`}
          hitSlop={6}
        >
          <Text variant="captionStrong" color={colors.green}>
            全部 {focus.facts.length} 条情报 · 展开 ›
          </Text>
        </Pressable>
      ) : expanded && focus.facts.length > 5 ? (
        <Pressable
          onPress={() => setExpanded(false)}
          accessibilityRole="button"
          accessibilityLabel="收起情报"
          hitSlop={6}
        >
          <Text variant="captionStrong" color={colors.muted}>收起 ›</Text>
        </Pressable>
      ) : null}
      {unknownVisible.map((item) => (
        <Text key={clean(item)} variant="caption" color={colors.subtle}>
          · 未确认：{clean(item)}
        </Text>
      ))}
      {!expanded && focus.unknowns.length > unknownVisible.length ? (
        <Pressable
          onPress={() => setExpanded(true)}
          accessibilityRole="button"
          accessibilityLabel="展开未确认项"
          hitSlop={6}
        >
          <Text variant="caption" color={colors.subtle}>
            还有 {focus.unknowns.length - unknownVisible.length} 项未确认 · 展开 ›
          </Text>
        </Pressable>
      ) : null}
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
  headRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  factRow: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  factBody: { flex: 1, gap: 1 },
  reason: { marginTop: 2 },
});
