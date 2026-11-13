import { memo, useCallback, useMemo, useState } from "react";
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Chip, ErrorState, Icon, Sheet, Skeleton, StatusDot, Text, useToast } from "@/components/ui";
import { useOnSaleQuery } from "@/features/home/queries";
import { useHideFloatingOnScroll } from "@/features/assistant/useHideFloatingOnScroll";
import { useWatchQuery } from "@/features/inbox/queries";
import { useParlayStore } from "@/features/tools/parlayStore";
import { onSaleStatusLabel } from "@/features/tools/onSaleStatus";
import { useWatchMatchMutation } from "@/features/verdict/queries";
import type { OnSaleItem } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { countdownText, currentTradeDateCn, formatDate, formatTime, pct, saleCountdownText, tradeDateCnFromKickoff } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Filter = "all" | "single" | "promoted" | "prediction";

/** 比赛行：memo 化，父层筛选/弹层状态变化不重绘所有行。 */
const MatchRow = memo(function MatchRow({
  item,
  now,
  onPress,
}: {
  item: OnSaleItem;
  now: number;
  onPress: (item: OnSaleItem) => void;
}) {
  return (
    <Pressable
      onPress={() => onPress(item)}
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
            {saleCountdownText(item.saleClose, now)}
            {item.rake != null ? ` · 抽水 ${pct(item.rake)}` : " · 抽水待同步"}
            {item.league ? ` · ${item.league}` : ""}
          </Text>
          {item.single ? <Chip label="单关" tone="green" /> : null}
        </View>
      </View>
      <View style={styles.status}>
        <StatusDot
          color={
            item.tier === "verified" || item.status === "promoted"
              ? colors.green
              : item.tier === "market_reference" || item.status === "screening"
                ? colors.amber
                : colors.subtle
          }
        />
        <Text variant="caption" color={colors.muted}>
          {onSaleStatusLabel(item.status, item.tier)}
        </Text>
      </View>
    </Pressable>
  );
});

/** 比赛 Tab：在售雷达 + 顶部串关入口；列表用 FlatList 虚拟化。 */
export default function MatchesScreen() {
  const router = useRouter();
  const toast = useToast();
  const query = useOnSaleQuery();
  const watchQuery = useWatchQuery();
  const watchMutation = useWatchMatchMutation();
  const onScroll = useHideFloatingOnScroll();
  const parlayCount = useParlayStore((s) => s.legs.length);
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<OnSaleItem | null>(null);
  const [pulling, setPulling] = useState(false);
  const now = useNow(60_000);
  const today = currentTradeDateCn(now);
  const watch = selected
    ? (watchQuery.data ?? []).find((item) => item.targetId === selected.matchId)
    : undefined;

  const rows = useMemo(() => {
    const list = query.data ?? [];
    return list.filter((item) => {
      if (filter === "single") return item.single;
      if (filter === "promoted") return item.status === "promoted";
      if (filter === "prediction") {
        return item.status === "screening" || item.tier === "market_reference";
      }
      return true;
    });
  }, [filter, query.data]);

  const open = useCallback((item: OnSaleItem) => {
    if (item.verdictId) {
      router.push({ pathname: "/verdict/[id]", params: { id: item.verdictId } });
      return;
    }
    // 没有判决的场次先给关注/详情，不直接跳走。
    setSelected(item);
  }, [router]);

  const renderRow = useCallback(
    ({ item }: { item: OnSaleItem }) => (
      <MatchRow item={item} now={now} onPress={open} />
    ),
    [now, open],
  );

  const listHeader = (
    <View>
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
          ["prediction", "预测"],
        ] as [Filter, string][]).map(([key, label]) => (
          <Chip key={key} label={label} selected={filter === key} onPress={() => setFilter(key)} />
        ))}
      </View>
    </View>
  );

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="比赛"
        subtitle={`${formatDate(today)} · 在售 ${query.data?.length ?? 0} 场`}
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
      <FlatList
        data={rows}
        keyExtractor={(item) => item.matchId}
        renderItem={renderRow}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={
          query.isLoading ? (
            <View style={styles.skeletons}>
              <Skeleton height={68} radius={16} />
              <Skeleton height={68} radius={16} />
              <Skeleton height={68} radius={16} />
            </View>
          ) : query.isError ? (
            <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
          ) : (
            <View style={styles.emptyWrap}>
              <Icon name="calendar-outline" size={28} color={colors.subtle} />
              <Text variant="body" color={colors.muted} center style={styles.empty}>
                当前筛选下没有在售场次。
              </Text>
            </View>
          )
        }
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
        onScroll={onScroll}
        scrollEventThrottle={48}
        showsVerticalScrollIndicator={false}
        initialNumToRender={8}
        maxToRenderPerBatch={10}
        windowSize={5}
        removeClippedSubviews
      />

      <Sheet
        visible={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.home} vs ${selected.away}` : "比赛"}
        subtitle={selected ? `${selected.matchNo} · ${formatTime(selected.saleClose)} 停售` : undefined}
        footer={
          selected ? (
            <View style={styles.sheetFooter}>
              <Button
                label={watch ? "取消关注" : "关注这场比赛"}
                variant={watch ? "secondary" : "primary"}
                loading={watchMutation.isPending}
                disabled={watchMutation.isPending}
                onPress={async () => {
                  if (watchMutation.isPending) return;
                  try {
                    await watchMutation.mutateAsync({
                      targetId: selected.matchId,
                      watching: Boolean(watch),
                      watchId: watch?.id,
                    });
                    toast.show(watch ? "已取消关注" : "已关注，停售和终场会提醒", "success");
                    setSelected(null);
                  } catch (e) {
                    toast.show(errorText(e), "error");
                  }
                }}
                fullWidth
              />
              <Button
                label="看三闸详情"
                variant="ghost"
                onPress={() => {
                  const item = selected;
                  setSelected(null);
                  if (item) {
                    router.push({
                      pathname: "/match/[id]",
                      params: { id: item.matchId, date: tradeDateCnFromKickoff(item.kickoff) },
                    });
                  }
                }}
                fullWidth
              />
            </View>
          ) : null
        }
      >
        {selected ? (
          <>
            <View style={styles.kv}>
              <Text variant="small" color={colors.muted}>比赛时间</Text>
              <Text variant="bodyStrong">{formatTime(selected.kickoff)}</Text>
            </View>
            <View style={styles.kv}>
              <Text variant="small" color={colors.muted}>停售时间</Text>
              <Text variant="bodyStrong">{formatTime(selected.saleClose)}（{countdownText(selected.saleClose, now)}）</Text>
            </View>
            <View style={styles.kv}>
              <Text variant="small" color={colors.muted}>抽水</Text>
              <Text variant="bodyStrong">{selected.rake != null ? pct(selected.rake) : "待同步"}</Text>
            </View>
            <View style={styles.kv}>
              <Text variant="small" color={colors.muted}>状态</Text>
              <Text variant="bodyStrong">
                {selected.status === "promoted"
                  ? "三关全过"
                  : selected.status === "screening"
                    ? "复核中"
                    : selected.status === "killed"
                      ? "本期不预测"
                      : "暂无预测"}
              </Text>
            </View>
            <Text variant="caption" color={colors.muted} style={styles.sheetNote}>
              这场还没出预测。关注后，停售前和终场会收到中性提醒；通知里不会出现队名和赔率。
            </Text>
          </>
        ) : null}
      </Sheet>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  filters: { flexDirection: "row", gap: spacing.xs, flexWrap: "wrap", marginTop: spacing.base },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    paddingVertical: spacing.base,
    paddingHorizontal: spacing.lg,
    minHeight: 72,
    marginTop: spacing.sm,
  },
  pressed: { opacity: 0.72 },
  time: { width: 54, gap: 2 },
  flex: { flex: 1, gap: 2 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, flexWrap: "wrap" },
  status: { alignItems: "center", gap: 2 },
  emptyWrap: { alignItems: "center", gap: spacing.md, marginTop: spacing.x6, paddingHorizontal: spacing.x4 },
  empty: { lineHeight: 22 },
  skeletons: { gap: spacing.sm, marginTop: spacing.base },
  sheetFooter: { gap: spacing.sm },
  kv: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  sheetNote: { marginTop: spacing.base, lineHeight: 18 },
});
