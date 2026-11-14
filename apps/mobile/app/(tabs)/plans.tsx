import { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Chip, EmptyState, ErrorState, Skeleton, Text } from "@/components/ui";
import {
  useMembershipQuery,
  usePlanCurrentQuery,
  usePlanHistoryQuery,
  usePlanSummaryQuery,
  type PlanBet,
  type PlanRisk,
} from "@/features/plans/queries";
import { errorText } from "@/lib/errors";
import { haptic } from "@/lib/haptics";
import { money, pct } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";

const RISKS: { key: PlanRisk; label: string }[] = [
  { key: "stable", label: "稳健定投" },
  { key: "balanced", label: "平衡定投" },
  { key: "aggressive", label: "进取定投" },
];

const BET_LABEL: Record<string, string> = {
  single: "单关",
  parlay: "2 串 1",
};

export default function PlansScreen() {
  const router = useRouter();
  const [risk, setRisk] = useState<PlanRisk>("stable");
  const [refreshing, setRefreshing] = useState(false);
  const summary = usePlanSummaryQuery();
  const current = usePlanCurrentQuery(risk);
  const history = usePlanHistoryQuery(risk);
  const membership = useMembershipQuery();

  const item = summary.data?.[risk];
  const plan = current.data?.plan;
  const locked = current.data?.locked ?? true;
  const tier = membership.data?.tier ?? current.data?.tier ?? "free";
  const refresh = async () => {
    haptic("light");
    setRefreshing(true);
    try {
      await Promise.all([summary.refetch(), current.refetch(), history.refetch(), membership.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const historyItems = useMemo(() => (history.data?.items ?? []).slice(0, 8), [history.data]);

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="计划"
        subtitle="AI 定投 · 模拟方案"
        showAssistant={false}
        right={<Chip label={tier === "free" ? "免费" : tier.toUpperCase()} tone={tier === "max" ? "green" : "neutral"} />}
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.green} />}
      >
        <Text variant="overline" color={colors.green}>AI 计划</Text>
        <Text variant="display" style={styles.title}>每期 4 场，每场 100</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          固定预算 400，可单关，也可把两场各 100 合成 2 串 1。只展示方案，不跟单。
        </Text>

        <View style={styles.riskRow}>
          {RISKS.map((r) => (
            <Chip
              key={r.key}
              label={r.label}
              selected={risk === r.key}
              onPress={() => setRisk(r.key)}
            />
          ))}
        </View>

        {summary.isLoading || summary.isPending || current.isLoading || current.isPending ? (
          <>
            <Skeleton height={150} radius={20} />
            <Skeleton height={220} radius={20} style={{ marginTop: spacing.base }} />
          </>
        ) : summary.isError || current.isError ? (
          <ErrorState message={errorText(summary.error ?? current.error)} onRetry={refresh} />
        ) : (
          <>
            <View style={styles.summaryCard}>
              <View style={styles.summaryHead}>
                <View style={styles.flex}>
                  <Text variant="overline" color={colors.greenAccent}>AI 模拟定投</Text>
                  <Text variant="h3" color={colors.inkInverse}>{item?.name ?? "稳健定投"}</Text>
                </View>
                <Text variant="caption" color={colors.mutedInverse}>
                  {item?.settled ?? 0} 期已结算
                </Text>
              </View>
              <Text
                variant="metric"
                color={(item?.pnl ?? 0) > 0 ? colors.greenAccent
                  : (item?.pnl ?? 0) < 0 ? colors.dangerAccent : colors.inkInverse}
              >
                {signed(item?.pnl ?? 0)}
              </Text>
              <Text variant="small" color={colors.mutedInverse}>
                累计模拟收益 · 近 7 天 {signed(item?.last_7d ?? 0)} · 近 30 天 {signed(item?.last_30d ?? 0)}
              </Text>
              {plan ? (
                <Text variant="caption" color={colors.mutedInverse}>
                  本期最大回撤 {plan.max_drawdown == null ? "—" : money(plan.max_drawdown)}
                </Text>
              ) : null}
              <Text variant="caption" color={colors.mutedInverse} style={styles.note}>
                历史模拟，不代表未来；只展示方案，不涉及真实资金。
              </Text>
            </View>

            {!plan ? (
              <EmptyState
                title="本期方案还没生成"
                body="一般 12:00 前更新。没有足够合格的场次时，不会为了凑 4 场硬做。"
                actionLabel="看比赛"
                onAction={() => router.push("/(tabs)/matches")}
              />
            ) : (
              <Card style={styles.planCard}>
                <View style={styles.summaryHead}>
                  <Text variant="h3">第 {plan.cycle_no} 期 · {plan.name}</Text>
                  <Chip label={plan.status === "settled" ? "已结算" : "进行中"} tone={plan.status === "settled" ? "green" : "amber"} />
                </View>
                <Text variant="caption" color={colors.muted}>
                  预算 {money(plan.budget)} · {plan.match_count} 场 · {plan.bet_count} 注
                </Text>
                <View style={styles.metrics}>
                  <Metric label="总投入" value={money(plan.total_stake)} />
                  <Metric label="当前盈亏" value={signed(plan.pnl)} tone={plan.pnl > 0 ? "green" : plan.pnl < 0 ? "danger" : "default"} />
                  <Metric label="回报率" value={plan.roi == null ? "—" : pct(plan.roi)} />
                </View>

                {locked ? (
                  <View style={styles.lock}>
                    <Text variant="bodyStrong">今日方案已生成，完整注单仅 Max 可见。</Text>
                    <Text variant="caption" color={colors.muted}>
                      Pro 含竞彩分析，不含 AI 计划；Max 可看完整方案。
                    </Text>
                    <Button label="了解 Max" variant="primary" onPress={() => router.push("/membership")} />
                  </View>
                ) : (
                  <View style={styles.bets}>
                    {plan.bets.map((bet) => <BetRow key={bet.id} bet={bet} />)}
                  </View>
                )}
              </Card>
            )}

            <View style={styles.sectionHead}>
              <Text variant="h3">历史期数</Text>
              <Text variant="caption" color={colors.muted}>{historyItems.length} 期</Text>
            </View>
            {historyItems.length === 0 ? (
              <Text variant="body" color={colors.muted} style={styles.emptyHistory}>
                还没有历史期数。计划页会从第一期开始积累。
              </Text>
            ) : (
              <Card padded={false}>
                {historyItems.map((cycle, index) => (
                  <Pressable
                    key={cycle.id}
                    onPress={() => router.push({ pathname: "/plans/[id]", params: { id: cycle.id } })}
                    style={({ pressed }) => [styles.historyRow, index < historyItems.length - 1 && styles.rowLine, pressed && styles.pressed]}
                  >
                    <View style={styles.flex}>
                      <Text variant="bodyStrong">第 {cycle.cycle_no} 期 · {cycle.name}</Text>
                      <Text variant="caption" color={colors.muted}>
                        {cycle.match_count} 场 · {cycle.bet_count} 注 · {cycle.status === "settled" ? "已结算" : "进行中"}
                      </Text>
                    </View>
                    <Text variant="bodyStrong" color={cycle.pnl > 0 ? colors.green : cycle.pnl < 0 ? colors.danger : colors.ink}>
                      {signed(cycle.pnl)}
                    </Text>
                  </Pressable>
                ))}
              </Card>
            )}
          </>
        )}
      </ScrollView>
    </AppScreen>
  );
}

function signed(value: number) {
  if (value === 0) return money(0);
  return `${value > 0 ? "+" : ""}${money(value)}`;
}

function Metric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "green" | "danger" }) {
  return (
    <View style={styles.metric}>
      <Text variant="caption" color={colors.muted}>{label}</Text>
      <Text variant="bodyStrong" color={tone === "green" ? colors.green : tone === "danger" ? colors.danger : colors.ink}>{value}</Text>
    </View>
  );
}

function BetRow({ bet }: { bet: PlanBet }) {
  return (
    <View style={styles.bet}>
      <View style={styles.betHead}>
        <Text variant="bodyStrong">{bet.label || BET_LABEL[bet.bet_type] || bet.bet_type}</Text>
        <Text variant="caption" color={colors.muted}>{money(bet.stake)} · @{bet.odds.toFixed(2)}</Text>
      </View>
      {bet.legs.map((leg) => (
        <View key={`${bet.id}-${leg.verdict_id}`} style={styles.leg}>
          <Text variant="caption" color={colors.muted}>
            {leg.match_no ? `${leg.match_no} · ` : ""}{leg.home} vs {leg.away}
          </Text>
          <Text variant="bodyStrong">{leg.direction} · {money(leg.allocation)}</Text>
          <Text variant="caption" color={colors.subtle}>{leg.selection_reason}</Text>
        </View>
      ))}
      <Text variant="caption" color={bet.pnl > 0 ? colors.green : bet.pnl < 0 ? colors.danger : colors.muted}>
        {bet.status === "pending" ? "待结算" : `${bet.status} · ${signed(bet.pnl)}`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: layout.tabBarHeight + spacing.x7 },
  title: { marginTop: 2 },
  lead: { marginTop: spacing.xs, lineHeight: 20 },
  riskRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.base, marginBottom: spacing.base, flexWrap: "wrap" },
  summaryCard: {
    gap: spacing.sm,
    backgroundColor: colors.heroBottom,
    borderWidth: 1,
    borderColor: colors.heroLine,
    borderRadius: radii.hero,
    padding: spacing.x4,
  },
  planCard: { marginTop: spacing.base, gap: spacing.sm },
  summaryHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  note: { lineHeight: 17 },
  metrics: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs },
  metric: { flex: 1, backgroundColor: colors.bgElevated, borderRadius: radii.md, padding: spacing.md, gap: 2 },
  lock: { backgroundColor: colors.amberSoft, borderRadius: radii.md, padding: spacing.base, gap: spacing.xs },
  bets: { gap: spacing.sm, marginTop: spacing.xs },
  bet: { backgroundColor: colors.bgElevated, borderRadius: radii.md, padding: spacing.base, gap: 3 },
  betHead: { flexDirection: "row", justifyContent: "space-between", gap: spacing.sm },
  leg: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line, paddingTop: spacing.xs, gap: 1 },
  sectionHead: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", marginTop: spacing.x4, marginBottom: spacing.sm },
  emptyHistory: { lineHeight: 20 },
  historyRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.lg, minHeight: 68 },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { opacity: 0.7 },
  flex: { flex: 1 },
});
