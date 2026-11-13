import { useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter, type Href } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { EmptyState, ErrorState, Skeleton, Text } from "@/components/ui";
import { useHideFloatingOnScroll } from "@/features/assistant/useHideFloatingOnScroll";
import { errorText } from "@/lib/errors";
import { todayCn, tradeDateCnFromKickoff } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";
import { DateNavigator } from "@/features/matches/components/DateNavigator";
import { LiveMatchCard, ResultMatchCard } from "@/features/matches/components/MatchCard";
import { AccuracyCard, PredictionMatchCard } from "@/features/matches/components/PredictionCard";
import { SegmentedTabs, type MatchTab } from "@/features/matches/components/SegmentedTabs";
import {
  useLiveBoardQuery,
  usePredictionHistoryQuery,
  useResultBoardQuery,
} from "@/features/matches/queries";

const SUBTITLES: Record<MatchTab, string> = {
  live: "只显示进行中的竞彩场次",
  results: "比分与半场，不含预测",
  predictions: "赛前锁定 · 赛后逐维对照",
};

interface Group<T> {
  title: string;
  data: T[];
}

function groupByLeague<T extends { league: string }>(items: T[]): Group<T>[] {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = item.league || "其他比赛";
    const list = groups.get(key);
    if (list) list.push(item);
    else groups.set(key, [item]);
  }
  return [...groups].map(([title, data]) => ({ title, data }));
}

export default function MatchesScreen() {
  const router = useRouter();
  const onScroll = useHideFloatingOnScroll();
  const [tab, setTab] = useState<MatchTab>("live");
  const [date, setDate] = useState(todayCn());
  const [pulling, setPulling] = useState(false);

  const live = useLiveBoardQuery(tab === "live");
  const results = useResultBoardQuery(date, tab === "results");
  const history = usePredictionHistoryQuery(date, tab === "predictions");

  const liveItems = useMemo(() => live.data?.matches ?? [], [live.data]);
  const resultItems = useMemo(() => results.data?.matches ?? [], [results.data]);
  const historyItems = useMemo(() => history.data?.matches ?? [], [history.data]);
  const liveGroups = useMemo(() => groupByLeague(liveItems), [liveItems]);
  const resultGroups = useMemo(() => groupByLeague(resultItems), [resultItems]);

  const refresh = async () => {
    setPulling(true);
    try {
      if (tab === "live") await live.refetch();
      else if (tab === "results") await results.refetch();
      else await history.refetch();
    } finally {
      setPulling(false);
    }
  };

  const active = tab === "live" ? live : tab === "results" ? results : history;

  return (
    <AppScreen bottom={false}>
      <AppHeader title="比赛" subtitle={SUBTITLES[tab]} />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        onScroll={onScroll}
        scrollEventThrottle={48}
        refreshControl={
          <RefreshControl refreshing={pulling} onRefresh={refresh} tintColor={colors.green} />
        }
      >
        <SegmentedTabs value={tab} onChange={setTab} liveCount={live.data?.count ?? 0} />

        {tab === "live" ? <LiveSummary count={live.data?.count ?? 0} /> : (
          <DateNavigator date={date} onChange={setDate} />
        )}

        {active.isLoading ? (
          <View style={styles.skeleton}>
            <Skeleton height={96} radius={16} />
            <Skeleton height={96} radius={16} />
            <Skeleton height={96} radius={16} />
          </View>
        ) : active.isError ? (
          <ErrorState message={errorText(active.error)} onRetry={() => active.refetch()} />
        ) : tab === "live" ? (
          liveItems.length === 0 ? (
            <EmptyState
              icon="pulse-outline"
              title="现在没有进行中的竞彩比赛"
              body="只有已映射到竞彩的场次会出现在这里；开赛后自动更新。"
              actionLabel="刷新"
              onAction={() => live.refetch()}
            />
          ) : (
            liveGroups.map((group) => (
              <Section key={group.title} group={group}>
                {group.data.map((item) => (
                  <LiveMatchCard
                    key={item.match_id}
                    match={item}
                    onPress={() =>
                      router.push({
                        pathname: "/match/[id]",
                        params: {
                          id: item.match_id,
                          date: tradeDateCnFromKickoff(item.kickoff),
                        },
                      })
                    }
                  />
                ))}
              </Section>
            ))
          )
        ) : tab === "results" ? (
          resultItems.length === 0 ? (
            <EmptyState
              icon="football-outline"
              title="这一天还没有赛果"
              body="已完赛场次同步后会出现在这里；没有拿到 FT90 比分就不展示。"
              actionLabel="刷新"
              onAction={() => results.refetch()}
            />
          ) : (
            resultGroups.map((group) => (
              <Section key={group.title} group={group} subtitle="FT90">
                {group.data.map((item) => (
                  <ResultMatchCard key={item.match_id} match={item} />
                ))}
              </Section>
            ))
          )
        ) : (
          <>
            {history.data ? <AccuracyCard summary={history.data.summary} /> : null}
            {historyItems.length === 0 ? (
              <EmptyState
                icon="analytics-outline"
                title="这一天还没有已结算预测"
                body="赛前锁定的预测在拿到赛果后逐条结算；没有赛前快照就不补造历史。"
                actionLabel="刷新"
                onAction={() => history.refetch()}
              />
            ) : (
              <View style={styles.historyList}>
                {historyItems.map((item) => (
                  <PredictionMatchCard
                    key={item.match_id}
                    match={item}
                    onPress={() =>
                      router.push(`/predictions/${item.match_id}` as Href)
                    }
                  />
                ))}
              </View>
            )}
          </>
        )}
      </ScrollView>
    </AppScreen>
  );
}

function LiveSummary({ count }: { count: number }) {
  return (
    <View style={styles.liveStrip}>
      <View style={[styles.liveDot, count === 0 && styles.idleDot]} />
      <Text variant="bodyStrong">{count > 0 ? `${count} 场进行中` : "等待开赛"}</Text>
      <Text variant="caption" color={colors.muted} style={styles.flex}>
        {count > 0 ? "30 秒自动刷新" : "开赛后自动出现"}
      </Text>
    </View>
  );
}

function Section<T>({
  group,
  subtitle,
  children,
}: {
  group: Group<T>;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        <Text variant="overline" color={colors.green}>{group.title}</Text>
        <Text variant="caption" color={colors.subtle}>
          {subtitle ? `${subtitle} · ` : ""}{group.data.length} 场
        </Text>
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.xs,
    paddingBottom: 40 + layout.tabBarHeight,
  },
  flex: { flex: 1 },
  liveStrip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
    minHeight: 48,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
  },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.green },
  idleDot: { backgroundColor: colors.subtle },
  section: { marginTop: spacing.xl },
  sectionHead: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  skeleton: { gap: spacing.sm, marginTop: spacing.xl },
  historyList: { marginTop: spacing.xs },
});
