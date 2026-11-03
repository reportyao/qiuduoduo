import { useCallback, useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AssistantHero } from "@/components/AssistantHero";
import { AppScreen } from "@/components/Screen";
import { Button, CardSkeleton, EmptyState, ErrorState, Text } from "@/components/ui";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useAuthStore } from "@/features/auth/authStore";
import { flattenStream, useOnSaleQuery, useStreamQuery } from "@/features/home/queries";
import { useBetsQuery } from "@/features/records/queries";
import {
  DataStatusBanner,
  ParlayBanner,
  SaleBanner,
} from "@/features/home/components/HomeBanners";
import { ChatComposer } from "@/features/home/components/ChatComposer";
import { MatchPickerSheet } from "@/features/home/components/MatchPickerSheet";
import {
  AvoidSection,
  DataStatusSheet,
  DateStrip,
  EmptyDayCard,
  FeedSummary,
  LegalFooter,
  PostmortemSection,
  RestDayCard,
} from "@/features/home/components/HomeSections";
import { VerdictCard } from "@/features/verdict/components/VerdictCard";
import { BetSheet } from "@/features/verdict/components/BetSheet";
import { SealSheet } from "@/features/verdict/components/SealSheet";
import { errorText } from "@/lib/errors";
import { currentTradeDateCn, relativeTime, shiftDateCn } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, spacing } from "@/theme/tokens";
import type { VerdictSummary } from "@/domain/types";

export default function HomeScreen() {
  const router = useRouter();
  const { copy } = usePersonaContent();
  const session = useAuthStore((s) => s.session);
  const [date, setDate] = useState(currentTradeDateCn());
  const [pickerOpen, setPickerOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [betTarget, setBetTarget] = useState<VerdictSummary | null>(null);
  const [sealTarget, setSealTarget] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);

  const streamQuery = useStreamQuery(date);
  const onsaleQuery = useOnSaleQuery();
  const betsQuery = useBetsQuery(Boolean(session));

  const { page: stream, verdicts } = useMemo(() => {
    const pages = streamQuery.data?.pages ?? [];
    if (pages.length === 0) return { page: null, verdicts: [] as VerdictSummary[] };
    return flattenStream(pages);
  }, [streamQuery.data]);

  const onsale = onsaleQuery.data ?? stream?.onsale ?? [];
  const betIds = useMemo(
    () => new Set((betsQuery.data ?? []).map((bet) => bet.verdictId)),
    [betsQuery.data],
  );

  const openVerdict = useCallback(
    (id: string) => router.push({ pathname: "/verdict/[id]", params: { id } }),
    [router],
  );
  const openWhyNot = useCallback(
    (matchId: string) => router.push({ pathname: "/match/[id]", params: { id: matchId, date } }),
    [date, router],
  );

  const refreshAll = async () => {
    setPulling(true);
    try {
      await Promise.all([
        streamQuery.refetch(),
        onsaleQuery.refetch(),
        betsQuery.refetch(),
      ]);
    } finally {
      setPulling(false);
    }
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="解球"
        subtitle={copy.brandSub}
        showAssistant={false}
        right={<Metrics stream={stream} />}
      />

      <View style={styles.flex}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              refreshing={pulling}
              onRefresh={refreshAll}
              tintColor={colors.green}
            />
          }
        >
          <AssistantHero onPress={() => setPickerOpen(true)} />
          <DateStrip value={date} onChange={setDate} />
          <DataStatusBanner stream={stream} onPress={() => setDataOpen(true)} />
          <SaleBanner onsale={onsale} onPress={() => router.push("/tools/on-sale")} />
          <ParlayBanner onPress={() => router.push("/tools/parlay")} />

          {streamQuery.isLoading ? (
            <>
              <CardSkeleton />
              <CardSkeleton />
            </>
          ) : streamQuery.isError && !stream ? (
            <ErrorState message={errorText(streamQuery.error)} onRetry={() => streamQuery.refetch()} />
          ) : !stream ? (
            <EmptyState
              title="今天的数据还没到"
              body="稍后下拉刷新，或先看看今日在售。"
              actionLabel="看今日在售"
              onAction={() => router.push("/tools/on-sale")}
            />
          ) : (
            <>
              <FeedSummary stream={stream} />
              {streamQuery.isError ? (
                <ErrorState
                  compact
                  message="刷新失败，先显示上次的结论。"
                  onRetry={() => streamQuery.refetch()}
                />
              ) : null}
              {stream.restDay ? (
                <RestDayCard rest={stream.restDay} onOpenLedger={() => router.push("/records/ledger")} />
              ) : verdicts.length === 0 ? (
                <EmptyDayCard
                  copyTitle={stream.stats.total === 0 ? copy.pendingTitle : copy.emptyTitle}
                  copyBody={stream.stats.total === 0 ? copy.pendingBody : copy.emptyBody}
                  onYesterday={() => setDate(shiftDateCn(currentTradeDateCn(), -1))}
                  onOnSale={() => router.push("/tools/on-sale")}
                />
              ) : (
                verdicts.map((verdict) => (
                  <VerdictCard
                    key={verdict.id}
                    verdict={verdict}
                    betExists={betIds.has(verdict.id)}
                    onOpen={openVerdict}
                    onBet={setBetTarget}
                    onWhyNot={openWhyNot}
                    onSeal={setSealTarget}
                  />
                ))
              )}

              {streamQuery.hasNextPage ? (
                <Button
                  label={streamQuery.isFetchingNextPage ? "加载中…" : "加载更多"}
                  variant="secondary"
                  onPress={() => streamQuery.fetchNextPage()}
                  loading={streamQuery.isFetchingNextPage}
                  style={styles.more}
                />
              ) : null}

              <AvoidSection items={stream.avoid} onOpen={openWhyNot} />
              <PostmortemSection items={stream.postmortems} onOpen={openVerdict} />
              <LegalFooter text={copy.footer} />
            </>
          )}
        </ScrollView>

        <ChatComposer onPress={() => router.push("/assistant")} />
      </View>

      <MatchPickerSheet
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        verdicts={verdicts}
        streamDate={stream?.tradeDate ?? date}
        onsale={onsale}
        onSelectVerdict={openVerdict}
        onSelectMatch={(matchId, tradeDate) =>
          router.push({
            pathname: "/match/[id]",
            params: { id: matchId, date: tradeDate || date },
          })
        }
      />
      <DataStatusSheet visible={dataOpen} onClose={() => setDataOpen(false)} stream={stream} />
      <BetSheet
        visible={Boolean(betTarget)}
        verdict={betTarget}
        you={stream?.you ?? null}
        onClose={() => setBetTarget(null)}
        onRecorded={() => {
          void betsQuery.refetch();
        }}
      />
      <SealSheet
        visible={Boolean(sealTarget)}
        verdictId={sealTarget}
        sealed={Boolean(verdicts.find((v) => v.id === sealTarget)?.sealed)}
        onClose={() => setSealTarget(null)}
      />
    </AppScreen>
  );
}

function Metrics({ stream }: { stream: ReturnType<typeof flattenStream>["page"] | null }) {
  const now = useNow(60_000);
  const total = stream?.stats.total ?? 0;
  return (
    <View style={styles.metrics}>
      <Text variant="captionStrong" color={colors.green}>三关 v3</Text>
      <Text variant="caption" color={colors.muted}>{total > 0 ? `${total * 3} 次核验` : "等待同步"}</Text>
      <Text variant="caption" color={colors.subtle}>
        {stream?.generatedAt ? relativeTime(stream.generatedAt, now) : "实时"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: {
    paddingHorizontal: layout.pagePadding,
    paddingBottom: 140,
  },
  metrics: { alignItems: "flex-end", gap: 0 },
  more: { marginTop: spacing.base },
});
