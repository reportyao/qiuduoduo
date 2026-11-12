import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Text, useToast } from "@/components/ui";
import { usePersonaContent } from "@/features/personas/usePersona";
import { usePrefsStore } from "@/features/preferences/prefsStore";
import { useAuthStore } from "@/features/auth/authStore";
import { useHideFloatingOnScroll } from "@/features/assistant/useHideFloatingOnScroll";
import {
  focusFromOnSale,
  focusFromVerdict,
  useFocusStore,
} from "@/features/home/focusStore";
import { useChatMutation } from "@/features/assistant/queries";
import { ChatCardContent, type ChatMessage } from "@/features/assistant/components/ChatCardContent";
import { useMemoryMutations } from "@/features/account/queries";
import { flattenStream, useEngineStatusQuery, useFocusQuery, useOnSaleQuery, usePulseQuery, useRecommendationsTodayQuery, useRecordSummaryQuery, useStreamQuery } from "@/features/home/queries";
import { useBetsQuery } from "@/features/records/queries";
import { trackInteraction } from "@/features/telemetry/interactions";
import { ChatComposer } from "@/features/home/components/ChatComposer";
import { MatchPickerSheet } from "@/features/home/components/MatchPickerSheet";
import type { BriefMatchOption } from "@/features/home/components/BriefMatchPicker";
import { buildBriefOptions } from "@/features/home/briefOptions";
import { FocusSection } from "@/features/home/components/FocusSection";
import { StreamFeed } from "@/features/home/components/StreamFeed";
import { HeaderMetrics } from "@/features/home/components/HeaderMetrics";
import { DataStatusSheet, LegalFooter } from "@/features/home/components/HomeSections";
import {
  AssistantMessage,
  AssistantTyping,
  ConversationDate,
} from "@/features/home/components/ConversationShell";
import {
  AssistantBrief,
  AvoidMessage,
  EmptyMessage,
  ErrorMessage,
  PostmortemMessage,
  RestMessage,
  UnattendedMessage,
} from "@/features/home/components/ConversationMessages";
import { BetSheet } from "@/features/verdict/components/BetSheet";
import { SealSheet } from "@/features/verdict/components/SealSheet";
import { ApiError, errorText } from "@/lib/errors";
import { currentTradeDateCn, formatDate, shiftDateCn } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, spacing } from "@/theme/tokens";
import type { VerdictSummary } from "@/domain/types";

/**
 * 首页 = 一条持续的对话流。
 * 助理先报今天的预测，再把每场预测作为消息逐条发出来；没给预测、复盘、休息日也都是消息。
 * 顶部只留身份与在线状态，头像常驻在 Tab 层，滚动时不打断对话。
 */
export default function HomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { copy, meta } = usePersonaContent();
  const toast = useToast();
  const chat = useChatMutation();
  const { save: saveMemory } = useMemoryMutations();
  const session = useAuthStore((s) => s.session);
  const [date, setDate] = useState(currentTradeDateCn());
  const [manualDate, setManualDate] = useState(false);
  const [openedAll, setOpenedAll] = useState(false);
  const now = useNow(60_000);
  const today = currentTradeDateCn(now);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [betTarget, setBetTarget] = useState<VerdictSummary | null>(null);
  const [sealTarget, setSealTarget] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);
  const focus = useFocusStore((s) => s.focus);
  const setFocus = useFocusStore((s) => s.setFocus);
  const clearFocus = useFocusStore((s) => s.clearFocus);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const lastDailyRecordDate = usePrefsStore((s) => s.lastDailyRecordDate);
  const setLastDailyRecordDate = usePrefsStore((s) => s.setLastDailyRecordDate);
  const prefsHydrated = usePrefsStore((s) => s.hydrated);
  const [recordVisible, setRecordVisible] = useState(false);
  const [confirmedConflicts, setConfirmedConflicts] = useState<string[]>([]);
  const scrollRef = useRef<ScrollView>(null);
  const autoScroll = useRef(false);
  const chatId = useRef(0);
  const nextChatId = (prefix: string) => {
    chatId.current += 1;
    return `${prefix}-${chatId.current}`;
  };

  const sendChat = (raw: string) => {
    const text = raw.trim();
    if (!text || chat.isPending) return;
    trackInteraction("free_text_send", { metadata: { length: text.length } });
    autoScroll.current = true;
    setChatMessages((prev) => [...prev, { id: nextChatId("u"), role: "user", text }]);
    const wantsAnalysis = ["分析", "这场", "依据", "怎么看", "风险"].some((hint) => text.includes(hint));
    chat.mutate({ text, matchId: wantsAnalysis ? focus?.matchId : undefined }, {
      onSuccess: (card) => {
        autoScroll.current = true;
        setChatMessages((prev) => [
          ...prev,
          { id: nextChatId("a"), role: "assistant", text: card.text, card },
        ]);
      },
      onError: (e) => {
        autoScroll.current = true;
        setChatMessages((prev) => [
          ...prev,
          { id: nextChatId("e"), role: "assistant", text: errorText(e), error: true },
        ]);
      },
    });
  };

  const confirmMemory = (messageId: string, key: string, value: string) => {
    if (saveMemory.isPending) return;
    saveMemory.mutate(
      { key, value, confirm: true },
      {
        onSuccess: () => {
          setConfirmedConflicts((prev) => (prev.includes(messageId) ? prev : [...prev, messageId]));
          toast.show("已覆盖记忆", "success");
          autoScroll.current = true;
          setChatMessages((prev) => [
            ...prev,
            { id: nextChatId("m"), role: "assistant", text: `已更新：${key} = ${value}。` },
          ]);
        },
        onError: (e) => toast.show(errorText(e), "error"),
      },
    );
  };

  // 头像常驻在 Tab 层；任意页面开始纵向阅读时收起，避免压住正文。
  const onScroll = useHideFloatingOnScroll();


  useEffect(() => {
    // 跨过 05:00 竞彩日界时，自动跟随“今天”；用户手动选了旧日期则不打扰。
    if (!manualDate && !focus && date !== today) setDate(today);
  }, [date, focus, manualDate, today]);

  const chooseDate = (next: string) => {
    setDate(next);
    setManualDate(next !== currentTradeDateCn());
    setOpenedAll(false);
    if (focus && focus.tradeDate !== next) clearFocus();
  };

  // 从别的 Tab 选中比赛后，首页要自动切到该场所属竞彩日。
  useEffect(() => {
    if (!focus || focus.tradeDate === date) return;
    setDate(focus.tradeDate);
    setManualDate(focus.tradeDate !== currentTradeDateCn());
    setOpenedAll(false);
  }, [date, focus]);

  // 选中/换场后回到聚焦区，不要停留在旧的滚动位置。
  useEffect(() => {
    if (!focus) return;
    const timer = setTimeout(() => {
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    }, 60);
    return () => clearTimeout(timer);
  }, [focus]);

  const streamQuery = useStreamQuery(date);
  const recommendationsQuery = useRecommendationsTodayQuery(date);
  const pulseQuery = usePulseQuery(date);
  const engineQuery = useEngineStatusQuery();
  const recordQuery = useRecordSummaryQuery();

  useEffect(() => {
    setRecordVisible(false);
  }, [today]);

  useEffect(() => {
    if (!prefsHydrated) return;
    const yesterday = recordQuery.data?.yesterday;
    if (!yesterday || yesterday.settled <= 0) return;
    if (lastDailyRecordDate === today) return;
    setRecordVisible(true);
    setLastDailyRecordDate(today);
  }, [lastDailyRecordDate, prefsHydrated, recordQuery.data, setLastDailyRecordDate, today]);
  const focusQuery = useFocusQuery(focus?.matchId ?? null, focus?.tradeDate ?? date, Boolean(focus));
  const onsaleQuery = useOnSaleQuery();
  const betsQuery = useBetsQuery(Boolean(session));

  const { page: stream, verdicts: streamVerdicts } = useMemo(() => {
    const pages = streamQuery.data?.pages ?? [];
    if (pages.length === 0) return { page: null, verdicts: [] as VerdictSummary[] };
    return flattenStream(pages);
  }, [streamQuery.data]);
  // 发布门：接口成功时只显示 published snapshot；只有旧后端 404 才回退 stream。
  // 加载中/网络错误/服务端错误都不能闪未复核的 raw verdict，避免把预览当成已发布内容。
  const publishedUnavailable = recommendationsQuery.error instanceof ApiError
    && recommendationsQuery.error.status === 404;
  const verdicts = useMemo(
    () => (recommendationsQuery.isSuccess
      ? recommendationsQuery.data.verdicts
      : publishedUnavailable
        ? streamVerdicts
        : []),
    [recommendationsQuery.data, recommendationsQuery.isSuccess,
     publishedUnavailable, streamVerdicts],
  );

  const onsale = useMemo(
    () => onsaleQuery.data ?? stream?.onsale ?? [],
    [onsaleQuery.data, stream?.onsale],
  );

  const references = useMemo(
    () => recommendationsQuery.data?.references ?? [],
    [recommendationsQuery.data],
  );

  // 开场选择条：已发布判决 + 市场参考 + 当前竞彩日在售，点哪场才展开哪场。
  const briefOptions = useMemo<BriefMatchOption[]>(
    () => buildBriefOptions(verdicts, references, date === today ? onsale : stream?.onsale ?? [], date),
    [date, onsale, references, stream?.onsale, today, verdicts],
  );

  const selectBriefOption = useCallback(
    (option: BriefMatchOption) => {
      setOpenedAll(false);
      const verdict = verdicts.find((item) => item.matchId === option.matchId)
        ?? references.find((item) => item.matchId === option.matchId);
      if (verdict) {
        trackInteraction("focus_select", {
          matchId: option.matchId,
          verdictId: verdict.id,
          metadata: { from: "brief" },
        });
        setFocus(focusFromVerdict(verdict, stream?.tradeDate ?? date));
        return;
      }
      const sourceOnsale = date === today ? onsale : stream?.onsale ?? [];
      const match = sourceOnsale.find((item) => item.matchId === option.matchId);
      if (match) {
        trackInteraction("focus_select", {
          matchId: option.matchId,
          metadata: { from: "brief" },
        });
        setFocus(focusFromOnSale(match, stream?.tradeDate ?? date));
        return;
      }
      router.push({ pathname: "/match/[id]", params: { id: option.matchId, date } });
    },
    [date, onsale, references, router, setFocus, stream?.onsale, stream?.tradeDate, today, verdicts],
  );

  const betIds = useMemo(
    () => new Set((betsQuery.data ?? []).map((bet) => bet.verdictId)),
    [betsQuery.data],
  );
  const focusedVerdict = useMemo(
    () => (focus?.verdictId
      ? verdicts.find((verdict) => verdict.id === focus.verdictId)
        ?? references.find((verdict) => verdict.id === focus.verdictId)
        ?? streamVerdicts.find((verdict) => verdict.id === focus.verdictId)
        ?? null
      : null),
    [focus?.verdictId, references, verdicts, streamVerdicts],
  );
  const heroVerdict = useMemo(() => {
    if (focus) return null;
    return verdicts.find((v) => v.status === "promoted")
      ?? verdicts.find((v) => v.status !== "killed" && Boolean(v.pick?.dir))
      ?? null;
  }, [focus, verdicts]);
  const restVerdicts = useMemo(
    () => (heroVerdict ? verdicts.filter((v) => v.id !== heroVerdict.id) : verdicts),
    [heroVerdict, verdicts],
  );

  // 曝光埋点：只记 Today Hero / 当前聚焦场，避免首屏几十张卡同时上报。
  const viewedKeys = useRef<Set<string>>(new Set());
  useEffect(() => {
    // 折叠态只显示选择条，不把未展示的 Hero 记成曝光。
    const v = focusedVerdict ?? (openedAll ? heroVerdict : null);
    if (!v) return;
    const key = v.snapshotId ?? v.id;
    if (viewedKeys.current.has(key)) return;
    viewedKeys.current.add(key);
    trackInteraction("verdict_viewed", {
      matchId: v.matchId,
      verdictId: v.id,
      metadata: { snapshot_id: v.snapshotId ?? null },
    });
  }, [focusedVerdict, heroVerdict, openedAll]);

  const openVerdict = useCallback(
    (id: string) => {
      trackInteraction("action_click", { verdictId: id, action: "open_detail" });
      router.push({ pathname: "/verdict/[id]", params: { id } });
    },
    [router],
  );
  const openWhyNot = useCallback(
    (matchId: string) => router.push({ pathname: "/match/[id]", params: { id: matchId, date } }),
    [date, router],
  );

  const focusSwitch = useCallback(() => setPickerOpen(true), []);
  const focusClearAll = useCallback(() => {
    clearFocus();
    setOpenedAll(true);
  }, [clearFocus]);
  const expandAll = useCallback(() => {
    clearFocus();
    setOpenedAll(true);
  }, [clearFocus]);
  const goMatches = useCallback(() => router.navigate("/(tabs)/matches"), [router]);

  const offerWhyNot = useCallback(() => {
    const target = stream?.avoid[0]?.matchId
      ?? verdicts.find((verdict) => verdict.status === "screening")?.matchId;
    if (target) openWhyNot(target);
    else router.push("/assistant");
  }, [openWhyNot, router, stream?.avoid, verdicts]);

  const refreshAll = async () => {
    setPulling(true);
    try {
      await Promise.all([
        streamQuery.refetch(),
        recommendationsQuery.refetch(),
        pulseQuery.refetch(),
        focusQuery.refetch(),
        onsaleQuery.refetch(),
        betsQuery.refetch(),
      ]);
    } finally {
      setPulling(false);
    }
  };

  const isEmptyDay = stream !== null && !stream.restDay && verdicts.length === 0;
  const viewingToday = date === today;
  const dayLabel = viewingToday ? "今天" : date === shiftDateCn(today, -1) ? "昨天" : formatDate(date);
  const emptyTitle = stream?.stats.total === 0
    ? viewingToday
      ? copy.pendingTitle
      : `${formatDate(date)}的预测还没出来。`
    : copy.emptyTitle;
  const emptyBody = stream?.stats.total === 0
    ? viewingToday
      ? copy.pendingBody
      : "这天的场次还没入库，或已经翻过去了。可以回今天，或先看今日在售。"
    : copy.emptyBody;
  // 有复核场次就先让助理报账；全部被砍时也要报总数，不能只剩一句“没有值得记的”。
  const briefStream = stream && !stream.restDay && (verdicts.length > 0 || stream.stats.total > 0)
    ? stream
    : null;

  return (
    <AppScreen bottom={false}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={0}
      >
        <ScrollView
          ref={scrollRef}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[
            styles.scrollContent,
            {
              paddingTop: insets.top,
              paddingBottom: layout.composerHeight + spacing.xl + Math.max(insets.bottom, 0) + spacing.x4,
            },
          ]}
          onContentSizeChange={() => {
            if (!autoScroll.current) return;
            autoScroll.current = false;
            scrollRef.current?.scrollToEnd({ animated: true });
          }}
          scrollEventThrottle={48}
          onScroll={onScroll}
          refreshControl={
            <RefreshControl
              refreshing={pulling}
              onRefresh={refreshAll}
              tintColor={colors.green}
            />
          }
        >
          {/* 顶部随对话滚走，不抢消息流；中间位置留给常驻助理头像 */}
          <AppHeader
            title="球多多"
            subtitle={copy.brandSub}
            showAssistant={false}
            insetTop={false}
            border={false}
            height={82}
            right={<HeaderMetrics engine={engineQuery.data ?? null} />}
          />

          <View style={styles.conversation}>
            <ConversationDate value={date} onChange={chooseDate} />

            {focus ? (
              <FocusSection
                focus={focus}
                focusData={focusQuery.data}
                focusLoading={focusQuery.isLoading}
                focusedVerdict={focusedVerdict}
                otherCount={verdicts.length - (focusedVerdict ? 1 : 0)}
                betExists={Boolean(focusedVerdict && betIds.has(focusedVerdict.id))}
                onOpenVerdict={openVerdict}
                onBet={setBetTarget}
                onWhyNot={openWhyNot}
                onSeal={setSealTarget}
                onSwitch={focusSwitch}
                onClearAll={focusClearAll}
                onOnSale={goMatches}
              />
            ) : null}

            {briefStream ? (
              <AssistantBrief
                stream={briefStream}
                dayLabel={dayLabel}
                publishedCount={recommendationsQuery.data?.snapshots.length ?? 0}
                publishedReady={recommendationsQuery.isSuccess}
                publishedMessage={recommendationsQuery.data?.message ?? null}
                referenceCount={references.length}
                recordText={recordVisible && recordQuery.data?.yesterday
                  ? copy.dailyRecord(
                      recordQuery.data.yesterday.picks,
                      recordQuery.data.yesterday.hits,
                      recordQuery.data.last_30_days.hit_days,
                    )
                  : null}
                onsaleCount={viewingToday ? onsale.length : briefStream.onsale.length}
                onsaleLabel={viewingToday ? "在售场次" : "当日场次"}
                options={briefOptions}
                optionsTotal={briefOptions.length}
                expanded={openedAll}
                onSelectOption={selectBriefOption}
                onExpandAll={expandAll}
                onPicker={() => setPickerOpen(true)}
                onOnSale={goMatches}
                onParlay={() => router.push({
                  pathname: "/tools/parlay",
                  params: { seed: String(Date.now()) },
                })}
                onWhyNot={offerWhyNot}
                onData={() => {
                  trackInteraction("pulse_open");
                  setDataOpen(true);
                }}
              />
            ) : null}

            {streamQuery.isLoading || (recommendationsQuery.isLoading && !recommendationsQuery.isError) ? (
              <AssistantTyping text={copy.typing} />
            ) : streamQuery.isError && !stream ? (
              <ErrorMessage
                message={errorText(streamQuery.error)}
                onRetry={() => streamQuery.refetch()}
              />
            ) : recommendationsQuery.isError && !publishedUnavailable ? (
              <ErrorMessage
                message={errorText(recommendationsQuery.error)}
                onRetry={() => recommendationsQuery.refetch()}
              />
            ) : !stream ? (
              <EmptyMessage
                title="今天的数据还没到"
                body="稍后下拉刷新，或先看看今日在售。"
                secondaryLabel="看昨日复盘"
                onSecondary={() => chooseDate(shiftDateCn(currentTradeDateCn(), -1))}
                onOnSale={goMatches}
              />
            ) : stream.restDay ? (
              <RestMessage
                rest={stream.restDay}
                title={viewingToday ? undefined : `${formatDate(date)}没有竞彩足球场次。`}
                onOpenLedger={() => router.push("/records/ledger")}
              />
            ) : isEmptyDay ? (
              <>
                {stream.stats.total === 0 ? (
                  <EmptyMessage
                    title={emptyTitle}
                    body={emptyBody}
                    secondaryLabel={viewingToday ? "看昨日复盘" : "回到今天"}
                    onSecondary={() =>
                      chooseDate(viewingToday ? shiftDateCn(currentTradeDateCn(), -1) : currentTradeDateCn())
                    }
                    onOnSale={goMatches}
                  />
                ) : null}
                {openedAll ? (
                  <>
                    <AvoidMessage items={stream.avoid} onOpen={openWhyNot} />
                    <PostmortemMessage items={stream.postmortems} onOpen={openVerdict} />
                    <UnattendedMessage items={stream.unattended} onOpen={openVerdict} />
                  </>
                ) : null}
              </>
            ) : (
              <>
                {streamQuery.isError ? (
                  <AssistantMessage>
                    <Text variant="small" color={colors.muted}>刷新失败，先显示上次的预测</Text>
                    <Pressable
                      onPress={() => streamQuery.refetch()}
                      accessibilityRole="button"
                      accessibilityLabel="重新刷新"
                      hitSlop={6}
                    >
                      <Text variant="captionStrong" color={colors.green} style={styles.retry}>重试 ›</Text>
                    </Pressable>
                  </AssistantMessage>
                ) : null}

                {(focus || openedAll) ? (
                  <StreamFeed
                    stream={stream}
                    heroVerdict={heroVerdict}
                    restVerdicts={restVerdicts}
                    betIds={betIds}
                    showRest={!focus}
                    hasNextPage={streamQuery.hasNextPage}
                    fetchingNext={streamQuery.isFetchingNextPage}
                    onOpenVerdict={openVerdict}
                    onBet={setBetTarget}
                    onWhyNot={openWhyNot}
                    onSeal={setSealTarget}
                    onParlay={() => router.push({ pathname: "/tools/parlay", params: { date } })}
                    onFetchNext={() => streamQuery.fetchNextPage()}
                  />
                ) : null}
              </>
            )}

            {!streamQuery.isLoading ? <LegalFooter text={copy.footer} /> : null}

            {chatMessages.length > 0 || chat.isPending ? (
              <View style={styles.chatThread}>
                {chatMessages.map((message) =>
                  message.role === "user" ? (
                    <View key={message.id} style={styles.userRow}>
                      <View style={styles.userBubble}>
                        <Text variant="small" color={colors.white}>{message.text}</Text>
                      </View>
                    </View>
                  ) : (
                    <AssistantMessage key={message.id}>
                      <ChatCardContent
                        message={message}
                        confirmed={confirmedConflicts.includes(message.id)}
                        savingMemory={saveMemory.isPending}
                        onOpenVerdict={openVerdict}
                        onConfirmMemory={(key, value) => confirmMemory(message.id, key, value)}
                      />
                    </AssistantMessage>
                  ),
                )}
                {chat.isPending ? <AssistantTyping text={`${meta.name}正在核对数据…`} /> : null}
              </View>
            ) : null}
          </View>
        </ScrollView>

        <ChatComposer
          onSend={sendChat}
          sending={chat.isPending}
        />
      </KeyboardAvoidingView>

      <MatchPickerSheet
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        verdicts={verdicts}
        streamDate={stream?.tradeDate ?? date}
        onsale={onsale}
        onSelectVerdict={(id) => {
          const verdict = verdicts.find((item) => item.id === id);
          if (verdict) {
            trackInteraction("focus_select", { matchId: verdict.matchId, verdictId: verdict.id });
            setFocus(focusFromVerdict(verdict, stream?.tradeDate ?? date));
            return;
          }
          const match = onsale.find((item) => item.verdictId === id);
          if (match) {
            trackInteraction("focus_select", { matchId: match.matchId, verdictId: id });
            setFocus(focusFromOnSale(match, stream?.tradeDate ?? date));
          } else openVerdict(id);
        }}
        onSelectMatch={(matchId, tradeDate) => {
          const match = onsale.find((item) => item.matchId === matchId);
          if (match) {
            trackInteraction("focus_select", { matchId: match.matchId });
            setFocus(focusFromOnSale(match, tradeDate || date));
          } else {
            router.push({
              pathname: "/match/[id]",
              params: { id: matchId, date: tradeDate || date },
            });
          }
        }}
      />
      <DataStatusSheet visible={dataOpen} onClose={() => setDataOpen(false)} stream={stream} pulse={pulseQuery.data} />
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

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scrollContent: { paddingBottom: spacing.x4 },
  conversation: {
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
  },
  chatThread: { marginTop: spacing.base },
  userRow: { alignItems: "flex-end", marginTop: spacing.sm },
  userBubble: {
    maxWidth: "82%",
    backgroundColor: colors.green,
    borderRadius: 18,
    borderBottomRightRadius: 6,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
  },
  retry: { marginTop: spacing.xs },
});
