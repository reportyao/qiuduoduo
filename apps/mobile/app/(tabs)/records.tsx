import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Chip, EmptyState, ErrorState, Skeleton, Text } from "@/components/ui";
import { useHideFloatingOnScroll } from "@/features/assistant/useHideFloatingOnScroll";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useAuthStore } from "@/features/auth/authStore";
import { useBetsQuery, useWeeklyQuery } from "@/features/records/queries";
import { PostmortemSheet } from "@/features/records/components/PostmortemSheet";
import { errorText } from "@/lib/errors";
import { money, pct, pickDirectionLabel, signedMoney } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";

export default function RecordsScreen() {
  const router = useRouter();
  const { copy } = usePersonaContent();
  const onScroll = useHideFloatingOnScroll();
  const session = useAuthStore((s) => s.session);
  const [postmortemId, setPostmortemId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const betsQuery = useBetsQuery(Boolean(session));
  const weeklyQuery = useWeeklyQuery(Boolean(session));
  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([betsQuery.refetch(), weeklyQuery.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };

  const bets = betsQuery.data ?? [];
  const settled = bets.filter((bet) => bet.pnl != null);
  const wins = settled.filter((bet) => bet.settled === "win").length;
  const week = weeklyQuery.data?.you;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="我的记录"
        subtitle="球多多 · AI 预测"
        showAssistant={false}
        right={<Chip label={session?.mode === "jwt" ? "已登录" : "设备账户"} tone="neutral" />}
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        onScroll={onScroll}
        scrollEventThrottle={48}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.green} />}
      >
        <View style={styles.stats}>
          <Stat label="本周注数" value={week ? String(week.bets) : "—"} sub={week ? "近 7 天 · 只记账" : "周报同步中"} />
          <Stat
            label="已结算"
            value={`${wins} / ${settled.length}`}
            sub={settled.length > 0 ? `命中 ${pct(wins / settled.length, 0)}` : "等待赛果"}
          />
          <Stat
            label="本周盈亏"
            value={week ? signedMoney(week.pnl) : "—"}
            sub={week ? "近 7 天真实盈亏" : "周报同步中"}
            tone={!week || week.pnl === 0 ? "default" : week.pnl > 0 ? "green" : "danger"}
          />
        </View>

        <View style={styles.actions}>
          <Button label="周报" variant="secondary" size="sm" onPress={() => router.push("/records/weekly")} style={styles.flex} />
          <Button label="公开账本" variant="secondary" size="sm" onPress={() => router.push("/records/ledger")} style={styles.flex} />
        </View>

        {weeklyQuery.isError ? (
          <ErrorState compact message="周报暂时取不到，票单仍可查看。" onRetry={() => weeklyQuery.refetch()} />
        ) : null}
        {betsQuery.isError && bets.length > 0 ? (
          <ErrorState compact message="刷新失败，先显示上次的票单。" onRetry={() => betsQuery.refetch()} />
        ) : null}
        <View style={styles.listHead}>
          <Text variant="h3">票单</Text>
          <Text variant="caption" color={colors.muted}>{bets.length} 注</Text>
        </View>

        {betsQuery.isLoading ? (
          <View style={{ gap: spacing.sm }}>
            <Skeleton height={70} radius={16} />
            <Skeleton height={70} radius={16} />
          </View>
        ) : betsQuery.isError && bets.length === 0 ? (
          <ErrorState message={errorText(betsQuery.error)} onRetry={() => betsQuery.refetch()} />
        ) : bets.length === 0 ? (
          <EmptyState
            title="还没有记过注"
            body="在首页三关全过的卡片上点「记一注」，这里就会出现你的真实记录。球多多只记账，不代购。"
            actionLabel="看今日预测"
            onAction={() => router.push("/(tabs)")}
            secondaryLabel="看公开账本"
            onSecondary={() => router.push("/records/ledger")}
          />
        ) : (
          <Card padded={false}>
            {bets.map((bet, index) => (
              <Pressable
                key={bet.id}
                onPress={() => setPostmortemId(bet.id)}
                accessibilityRole="button"
                accessibilityLabel={`${bet.match} 复盘`}
                style={({ pressed }) => [
                  styles.row,
                  index < bets.length - 1 && styles.rowLine,
                  pressed && styles.pressed,
                ]}
              >
                <View style={styles.flex}>
                  <Text variant="caption" color={colors.subtle}>{bet.matchNo}</Text>
                  <Text variant="bodyStrong" numberOfLines={1}>{bet.match}</Text>
                  <Text variant="caption" color={colors.muted}>
                    {pickDirectionLabel(bet.pool, bet.pickDir)}
                    {bet.goalLine ? `（${bet.goalLine}）` : ""} · {money(bet.amount)}
                  </Text>
                </View>
                <View style={styles.right}>
                  <Chip
                    label={bet.settled === "win" ? "✓ 中" : bet.settled === "lose" ? "× 未中" : "待结算"}
                    tone={bet.settled === "win" ? "green" : bet.settled === "lose" ? "danger" : "neutral"}
                  />
                  <Text
                    variant="smallStrong"
                    color={bet.pnl == null ? colors.muted : bet.pnl >= 0 ? colors.green : colors.danger}
                  >
                    {bet.pnl == null ? "—" : signedMoney(bet.pnl)}
                  </Text>
                </View>
              </Pressable>
            ))}
          </Card>
        )}

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>{copy.footer}</Text>
      </ScrollView>

      <PostmortemSheet betId={postmortemId} onClose={() => setPostmortemId(null)} />
    </AppScreen>
  );
}

function Stat({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "default" | "green" | "danger";
}) {
  return (
    <View style={styles.stat}>
      <Text variant="caption" color={colors.muted}>{label}</Text>
      <Text variant="h2" color={tone === "green" ? colors.green : tone === "danger" ? colors.danger : colors.ink}>
        {value}
      </Text>
      <Text variant="caption" color={colors.subtle}>{sub}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  stats: { flexDirection: "row", gap: spacing.sm },
  stat: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.base,
    minHeight: 92,
    gap: 2,
  },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.base },
  flex: { flex: 1 },
  listHead: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", marginTop: spacing.x4, marginBottom: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    padding: spacing.base,
    paddingHorizontal: spacing.xl,
    minHeight: 74,
  },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { backgroundColor: colors.bgElevated },
  right: { alignItems: "flex-end", gap: 4 },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
});
