import { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Chip, ErrorState, Skeleton, StatusDot, Text } from "@/components/ui";
import { useOnSaleQuery } from "@/features/home/queries";
import { useParlayStore } from "@/features/tools/parlayStore";
import { onSaleStatusLabel } from "@/features/tools/onSaleStatus";
import type { OnSaleItem } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { countdownText, currentTradeDateCn, formatTime, pct, tradeDateCnFromKickoff } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Filter = "all" | "single" | "promoted" | "screening";

/** 比赛 Tab：在售雷达 + 顶部串关入口。 */
export default function MatchesScreen() {
  const router = useRouter();
  const query = useOnSaleQuery();
  const parlayCount = useParlayStore((s) => s.legs.length);
  const [filter, setFilter] = useState<Filter>("all");
  const [pulling, setPulling] = useState(false);
  const now = useNow(60_000);
  const today = currentTradeDateCn(now);

  const rows = useMemo(() => {
    const list = query.data ?? [];
    return list.filter((item) => {
      if (filter === "single") return item.single;
      if (filter === "promoted") return item.status === "promoted";
      if (filter === "screening") return item.status === "screening";
      return true;
    });
  }, [filter, query.data]);

  const open = (item: OnSaleItem) => {
    if (item.verdictId) {
      router.push({ pathname: "/verdict/[id]", params: { id: item.verdictId } });
      return;
    }
    router.push({
      pathname: "/match/[id]",
      params: { id: item.matchId, date: tradeDateCnFromKickoff(item.kickoff) },
    });
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="比赛"
        subtitle={`${today} · 在售 ${query.data?.length ?? 0} 场`}
        right={
          <Button
            label={parlayCount > 0 ? `串关 ${parlayCount}` : "串关"}
            variant={parlayCount > 0 ? "primary" : "secondary"}
            size="sm"
            onPress={() =>
              router.push({ pathname: "/tools/parlay", params: { seed: String(Date.now()) } })
            }
            accessibilityHint="打开串关参谋"
          />
        }
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={pulling}
            onRefresh={async () => {
              setPulling(true);
              try {
                await query.refetch();
              } finally {
                setPulling(false);
              }
            }}
            tintColor={colors.green}
          />
        }
      >
        <Text variant="overline" color={colors.green}>在售 · 官方停售时间</Text>
        <Text variant="display" style={styles.title}>今天能看的场</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          停售时刻 = 官方开赛时刻。点一场看三闸与依据；也可以先加入串关，最多 6 场。
        </Text>

        <View style={styles.filters}>
          {([
            ["all", "全部"],
            ["single", "单关"],
            ["promoted", "已发布"],
            ["screening", "复核中"],
          ] as [Filter, string][]).map(([key, label]) => (
            <Chip key={key} label={label} selected={filter === key} onPress={() => setFilter(key)} />
          ))}
        </View>

        {query.isLoading ? (
          <View style={styles.skeletons}>
            <Skeleton height={68} radius={16} />
            <Skeleton height={68} radius={16} />
            <Skeleton height={68} radius={16} />
          </View>
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : rows.length === 0 ? (
          <Text variant="body" color={colors.muted} style={styles.empty}>
            当前筛选下没有在售场次。可能是休息日，或数据还没同步。
          </Text>
        ) : (
          <View style={styles.list}>
            {rows.map((item) => (
              <Pressable
                key={item.matchId}
                onPress={() => open(item)}
                accessibilityRole="button"
                accessibilityLabel={`${item.home} 对 ${item.away}，${formatTime(item.kickoff)} 开赛`}
                style={({ pressed }) => [styles.row, pressed && styles.pressed]}
              >
                <View style={styles.time}>
                  <Text variant="bodyStrong">{formatTime(item.kickoff)}</Text>
                  <Text variant="caption" color={colors.subtle}>{item.matchNo}</Text>
                </View>
                <View style={styles.flex}>
                  <Text variant="bodyStrong" numberOfLines={1}>
                    {item.home} <Text variant="caption" color={colors.muted}>vs</Text> {item.away}
                  </Text>
                  <View style={styles.metaRow}>
                    <Text variant="caption" color={colors.muted}>
                      {countdownText(item.saleClose, now)}停售
                      {item.rake != null ? ` · 抽水 ${pct(item.rake)}` : " · 待复核"}
                      {item.league ? ` · ${item.league}` : ""}
                    </Text>
                    {item.single ? <Chip label="单关" tone="green" /> : null}
                  </View>
                </View>
                <View style={styles.status}>
                  <StatusDot
                    color={
                      item.status === "promoted"
                        ? colors.green
                        : item.status === "screening"
                          ? colors.amber
                          : item.status === "killed"
                            ? colors.danger
                            : colors.subtle
                    }
                  />
                  <Text variant="caption" color={item.status === "killed" ? colors.danger : colors.muted}>
                    {onSaleStatusLabel(item.status)}
                  </Text>
                </View>
              </Pressable>
            ))}
          </View>
        )}
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  filters: { flexDirection: "row", gap: spacing.xs, flexWrap: "wrap", marginTop: spacing.base },
  list: { gap: spacing.sm, marginTop: spacing.base },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.base,
    minHeight: 68,
  },
  pressed: { opacity: 0.72 },
  time: { width: 50, gap: 1 },
  flex: { flex: 1, gap: 2 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, flexWrap: "wrap" },
  status: { alignItems: "center", gap: 2 },
  empty: { marginTop: spacing.x4, lineHeight: 22 },
  skeletons: { gap: spacing.sm, marginTop: spacing.base },
});
