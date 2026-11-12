import { ScrollView, StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Chip, ErrorState, Skeleton, Text } from "@/components/ui";
import { usePlanCycleQuery, type PlanBet } from "@/features/plans/queries";
import { goBackOr } from "@/lib/navigation";
import { errorText } from "@/lib/errors";
import { money, pct } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";

export default function PlanDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const query = usePlanCycleQuery(id ?? "");
  const data = query.data;
  const plan = data?.plan;
  const locked = data?.locked ?? true;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="方案详情"
        subtitle="AI 定投 · 模拟方案"
        showAssistant={false}
        onBack={() => goBackOr(router)}
        backLabel="返回"
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {query.isLoading || query.isPending ? (
          <>
            <Skeleton height={180} radius={20} />
            <Skeleton height={260} radius={20} style={{ marginTop: spacing.base }} />
          </>
        ) : query.isError || !plan ? (
          <ErrorState message={query.isError ? errorText(query.error) : "方案不存在"} onRetry={() => query.refetch()} />
        ) : (
          <>
            <Card style={styles.head}>
              <View style={styles.row}>
                <Text variant="h2">第 {plan.cycle_no} 期 · {plan.name}</Text>
                <Chip label={plan.status === "settled" ? "已结算" : "进行中"} tone={plan.status === "settled" ? "green" : "amber"} />
              </View>
              <Text variant="caption" color={colors.muted}>
                预算 {money(plan.budget)} · {plan.match_count} 场 · {plan.bet_count} 注
              </Text>
              <View style={styles.metrics}>
                <Metric label="总投入" value={money(plan.total_stake)} />
                <Metric label="盈亏" value={signed(plan.pnl)} tone={plan.pnl > 0 ? "green" : plan.pnl < 0 ? "danger" : "default"} />
                <Metric label="回报率" value={plan.roi == null ? "—" : pct(plan.roi)} />
              </View>
              <Text variant="caption" color={colors.muted}>
                最大回撤 {plan.max_drawdown == null ? "—" : money(plan.max_drawdown)}
              </Text>
            </Card>

            {locked ? (
              <Card style={styles.lock}>
                <Text variant="bodyStrong">完整方案仅 Max 可见。</Text>
                <Text variant="caption" color={colors.muted}>Pro 含竞彩分析，不含 AI 计划。</Text>
                <Button label="了解 Max" variant="primary" onPress={() => router.push("/membership")} />
              </Card>
            ) : (
              plan.bets.map((bet) => <BetCard key={bet.id} bet={bet} />)
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

function BetCard({ bet }: { bet: PlanBet }) {
  return (
    <Card style={styles.bet}>
      <View style={styles.row}>
        <Text variant="bodyStrong">{bet.label || bet.bet_type}</Text>
        <Text variant="caption" color={colors.muted}>{money(bet.stake)} · @{bet.odds.toFixed(2)}</Text>
      </View>
      {bet.legs.map((leg) => (
        <View key={`${bet.id}-${leg.verdict_id}`} style={styles.leg}>
          <Text variant="caption" color={colors.muted}>
            {leg.match_no ? `${leg.match_no} · ` : ""}{leg.home} vs {leg.away}
          </Text>
          <Text variant="bodyStrong">{leg.direction} · 分配 {money(leg.allocation)}</Text>
          <Text variant="caption" color={colors.subtle}>{leg.selection_reason}</Text>
        </View>
      ))}
      <Text variant="caption" color={bet.pnl > 0 ? colors.green : bet.pnl < 0 ? colors.danger : colors.muted}>
        {bet.status === "pending" ? "待结算" : `${bet.status} · ${signed(bet.pnl)}`}
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7, gap: spacing.base },
  head: { gap: spacing.xs },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  metrics: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs },
  metric: { flex: 1, backgroundColor: colors.bgElevated, borderRadius: radii.md, padding: spacing.sm, gap: 2 },
  lock: { backgroundColor: colors.amberSoft, gap: spacing.xs },
  bet: { gap: spacing.xs },
  leg: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line, paddingTop: spacing.xs, gap: 1 },
});
