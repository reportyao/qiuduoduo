import { useMemo } from "react";
import { goBackOr } from "@/lib/navigation";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  IconButton,
  Skeleton,
  Text,
  useToast,
} from "@/components/ui";
import { useRemoveWatchMutation, useWatchQuery } from "@/features/inbox/queries";
import { useStreamQuery } from "@/features/home/queries";
import { errorText } from "@/lib/errors";
import { countdownText, currentTradeDateCn, formatDate, formatTime, tradeDateCnFromKickoff } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, spacing } from "@/theme/tokens";

export default function WatchScreen() {
  const router = useRouter();
  const toast = useToast();
  const now = useNow(30_000);
  const query = useWatchQuery();
  const streamQuery = useStreamQuery(currentTradeDateCn());
  const remove = useRemoveWatchMutation();
  const watched = query.data ?? [];
  const verdictByMatch = useMemo(() => {
    const map = new Map<string, string>();
    for (const verdict of streamQuery.data?.pages[0]?.verdicts ?? []) {
      map.set(verdict.matchId, verdict.id);
    }
    return map;
  }, [streamQuery.data]);

  const open = (matchId: string) => {
    const verdictId = verdictByMatch.get(matchId);
    if (verdictId) {
      router.push({ pathname: "/verdict/[id]", params: { id: verdictId } });
      return;
    }
    const item = watched.find((row) => row.targetId === matchId);
    const date = item?.kickoff ? tradeDateCnFromKickoff(item.kickoff) : currentTradeDateCn();
    router.push({ pathname: "/match/[id]", params: { id: matchId, date } });
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="关注"
        subtitle="只推你关注的比赛"
        showAssistant={false}
        onBack={() => goBackOr(router)}
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={query.isRefetching} onRefresh={() => query.refetch()} tintColor={colors.green} />
        }
      >
        {query.isError && watched.length > 0 ? (
          <ErrorState compact message="刷新失败，先显示上次的关注。" onRetry={() => query.refetch()} />
        ) : null}
        <Text variant="overline" color={colors.green}>关注列表</Text>
        <Text variant="h2" style={styles.title}>{watched.length} 场</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          关注后，预测更新、停售和终场会出现在收件箱。锁屏推送不会出现队名和赔率。
        </Text>

        {query.isLoading ? (
          <View style={{ gap: spacing.sm, marginTop: spacing.base }}>
            <Skeleton height={82} radius={18} />
            <Skeleton height={82} radius={18} />
          </View>
        ) : query.isError && watched.length === 0 ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : watched.length === 0 ? (
          <EmptyState
            icon="heart-outline"
            title="还没有关注比赛"
            body="在比赛详情页点底部的心形，就能收到停售和终场提醒。也可以从助理的比赛选择器进入。"
            actionLabel="看今日比赛"
            onAction={() => router.push("/(tabs)")}
          />
        ) : (
          <View style={styles.list}>
            {watched.map((item) => (
              <Card key={item.id} style={styles.row}>
                <Pressable
                  onPress={() => open(item.targetId)}
                  accessibilityRole="button"
                  accessibilityLabel={item.home ? `${item.home} 对 ${item.away}` : item.targetId}
                  style={styles.flex}
                >
                  <Text variant="bodyStrong">
                    {item.home && item.away ? `${item.home} vs ${item.away}` : item.targetId}
                  </Text>
                  <Text variant="caption" color={colors.muted}>
                    {item.matchNo ?? "比赛"} ·{" "}
                    {item.kickoff
                      ? `${formatDate(item.kickoff)} ${formatTime(item.kickoff)} · ${closeLabel(item.kickoff, now)}`
                      : "时间待同步"}
                  </Text>
                  <View style={styles.chips}>
                    <Chip label="预测更新" tone="green" />
                    <Chip label="终场" tone="neutral" />
                  </View>
                </Pressable>
                <IconButton
                  name="trash-outline"
                  size={17}
                  accessibilityLabel="取消关注"
                  onPress={async () => {
                    if (remove.isPending) return;
                    try {
                      await remove.mutateAsync(item.id);
                      toast.show("已取消关注", "info");
                    } catch (e) {
                      toast.show(errorText(e), "error");
                    }
                  }}
                />
              </Card>
            ))}
          </View>
        )}

        <Button label="去看今日预测" variant="secondary" onPress={() => router.push("/(tabs)")} fullWidth style={styles.more} />
      </ScrollView>
    </AppScreen>
  );
}

function closeLabel(kickoff: string, now: number): string {
  const text = countdownText(kickoff, now);
  return text === "已停售" ? text : `${text}停售`;
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  list: { gap: spacing.sm, marginTop: spacing.base },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.base },
  flex: { flex: 1, gap: 3 },
  chips: { flexDirection: "row", gap: spacing.xs, flexWrap: "wrap", marginTop: 2 },
  more: { marginTop: spacing.base },
});
