import { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import {
  Button,
  Chip,
  ErrorState,
  Sheet,
  Skeleton,
  StatusDot,
  Text,
  useToast,
} from "@/components/ui";
import { useOnSaleQuery } from "@/features/home/queries";
import { useWatchQuery } from "@/features/inbox/queries";
import { useWatchMatchMutation } from "@/features/verdict/queries";
import type { OnSaleItem } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { countdownText, formatTime, pct, tradeDateCnFromKickoff } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Filter = "all" | "single" | "promoted" | "screening";

export default function OnSaleScreen() {
  const router = useRouter();
  const toast = useToast();
  const query = useOnSaleQuery();
  const watchQuery = useWatchQuery();
  const watchMutation = useWatchMatchMutation();
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<OnSaleItem | null>(null);
  const [pulling, setPulling] = useState(false);

  const rows = useMemo(() => {
    const list = query.data ?? [];
    return list.filter((item) => {
      if (filter === "single") return item.single;
      if (filter === "promoted") return item.status === "promoted";
      if (filter === "screening") return item.status === "screening";
      return true;
    });
  }, [filter, query.data]);

  const watch = selected
    ? (watchQuery.data ?? []).find((item) => item.targetId === selected.matchId)
    : undefined;

  const open = (item: OnSaleItem) => {
    if (item.verdictId) {
      router.push({ pathname: "/verdict/[id]", params: { id: item.verdictId } });
    } else if (item.status === "screening" || item.status === "killed") {
      router.push({ pathname: "/match/[id]", params: { id: item.matchId, date: tradeDateCnFromKickoff(item.kickoff) } });
    } else {
      setSelected(item);
    }
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader title="今日在售" showAssistant={false} onBack={() => router.back()} />
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
        <Text variant="display" style={styles.title}>今天能看的场。</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          竞彩足球停售时刻 = 官方开赛时刻。凌晨场次会在前一晚截止，别把日期看错。
        </Text>

        <View style={styles.filters}>
          {([
            ["all", "全部"],
            ["single", "单关"],
            ["promoted", "过三关"],
            ["screening", "复核中"],
          ] as [Filter, string][]).map(([key, label]) => (
            <Chip key={key} label={label} selected={filter === key} onPress={() => setFilter(key)} />
          ))}
        </View>

        {query.isLoading ? (
          <View style={{ gap: spacing.sm, marginTop: spacing.base }}>
            <Skeleton height={64} radius={16} />
            <Skeleton height={64} radius={16} />
            <Skeleton height={64} radius={16} />
          </View>
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : rows.length === 0 ? (
          <Text variant="body" color={colors.muted} style={styles.empty}>
            当前筛选下没有场次。今天可能已经停售，或数据还没同步。
          </Text>
        ) : (
          <View style={styles.list}>
            {rows.map((item) => (
              <Pressable
                key={item.matchId}
                onPress={() => open(item)}
                accessibilityRole="button"
                accessibilityLabel={`${item.home} 对 ${item.away}`}
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
                      {countdownText(item.saleClose)}停售 · {item.rake != null ? `抽水 ${pct(item.rake)}` : "尚未复核"}
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
                          : colors.subtle
                    }
                  />
                  <Text variant="caption" color={colors.muted}>
                    {item.status === "promoted" ? "已过" : item.status === "screening" ? "复核" : "在售"}
                  </Text>
                </View>
              </Pressable>
            ))}
          </View>
        )}
      </ScrollView>

      <Sheet
        visible={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.home} vs ${selected.away}` : "比赛"}
        subtitle={selected ? `${selected.matchNo} · ${formatTime(selected.saleClose)} 停售` : undefined}
        footer={
          selected ? (
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
              <Text variant="bodyStrong">{formatTime(selected.saleClose)}（{countdownText(selected.saleClose)}）</Text>
            </View>
            <View style={styles.kv}>
              <Text variant="small" color={colors.muted}>抽水</Text>
              <Text variant="bodyStrong">{selected.rake != null ? pct(selected.rake) : "待同步"}</Text>
            </View>
            <View style={styles.kv}>
              <Text variant="small" color={colors.muted}>状态</Text>
              <Text variant="bodyStrong">
                {selected.status === "promoted" ? "三关全过" : selected.status === "screening" ? "复核中" : "暂无判断"}
              </Text>
            </View>
            <Text variant="caption" color={colors.muted} style={styles.sheetNote}>
              这场还没出结论。关注后，停售前和终场会收到中性提醒；通知里不会出现队名和赔率。
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
