import { useEffect, useMemo, useRef, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Clipboard from "expo-clipboard";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import {
  Button,
  CardSkeleton,
  ErrorState,
  Stepper,
  Text,
  useToast,
} from "@/components/ui";
import { useRecommendationsTodayQuery, useStreamQuery } from "@/features/home/queries";
import { useOddsFormat } from "@/features/preferences/prefsStore";
import { DateStrip } from "@/features/home/components/HomeSections";
import { ParlayReport } from "@/features/tools/ParlayReport";
import { ParlayPlans } from "@/features/tools/ParlayPlans";
import { useParlayCheckMutation, useParlayPlanMutation, type ParlayCheck, type ParlayPlan } from "@/features/tools/queries";
import { PARLAY_MAX_LEGS, useParlayStore } from "@/features/tools/parlayStore";
import type { VerdictSummary } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { currentTradeDateCn, decimalToFormat, oddsFormatLabel, pct, pickDirectionLabel, shiftDateCn } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Dir = "home" | "draw" | "away";
type Selection = Record<string, Dir>;

const DIR_LABEL: Record<Dir, string> = { home: "主胜", draw: "平", away: "客胜" };
const DIR_KEY: Record<Dir, "h" | "d" | "a"> = { home: "h", draw: "d", away: "a" };

export default function ParlayToolScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ date?: string; seed?: string }>();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const oddsFormat = useOddsFormat();
  const [selection, setSelection] = useState<Selection>({});
  const [reportOpen, setReportOpen] = useState(false);
  const [report, setReport] = useState<ParlayCheck | null>(null);
  const [planData, setPlanData] = useState<ParlayPlan | null>(null);
  const [planReviewed, setPlanReviewed] = useState(false);
  const [stake, setStake] = useState(100);
  const check = useParlayCheckMutation();
  const plan = useParlayPlanMutation();
  const storeLegs = useParlayStore((s) => s.legs);
  const removeStoreLeg = useParlayStore((s) => s.remove);
  const clearStore = useParlayStore((s) => s.clear);
  const scrollRef = useRef<ScrollView>(null);
  const reportY = useRef(0);
  const pendingScroll = useRef(false);
  const checkSeq = useRef(0);
  const [date, setDate] = useState(params.date || currentTradeDateCn());
  const [manualDate, setManualDate] = useState(false);
  const now = useNow(60_000);
  const today = currentTradeDateCn(now);
  useEffect(() => {
    if (!manualDate && date !== today) setDate(today);
  }, [date, manualDate, today]);
  const chooseDate = (next: string) => {
    setDate(next);
    setManualDate(next !== currentTradeDateCn());
  };
  const streamQuery = useStreamQuery(date);
  const recommendationsQuery = useRecommendationsTodayQuery(date);
  const stream = streamQuery.data?.pages[0];

  const matches = useMemo(
    () => (stream?.verdicts ?? []).filter(
      (v) => v.rake != null && v.sp.h > 1 && v.sp.d > 1 && v.sp.a > 1,
    ),
    [stream],
  );
  // 从详情页“加入串关”带 seed 进来时，把共享腿池合并进本页选择。
  useEffect(() => {
    if (!params.seed || matches.length === 0) return;
    setSelection((prev) => {
      const next = { ...prev };
      const ids = new Set(matches.map((match) => match.id));
      for (const leg of storeLegs) {
        if (leg.tradeDate !== date || !ids.has(leg.verdictId)) continue;
        if (Object.keys(next).length >= PARLAY_MAX_LEGS) break;
        next[leg.verdictId] = leg.dir;
      }
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.seed, matches, date]);

  const legs = useMemo(
    () =>
      Object.entries(selection)
        .map(([id, dir]) => {
          const match = matches.find((m) => m.id === id);
          // 没有抽水快照的复核场不能当 0 成本参与串关，否则返还率会被高估。
          if (!match || match.rake == null) return null;
          return {
            match,
            dir,
            odds: match.sp[DIR_KEY[dir]],
            rake: match.rake,
          };
        })
        .filter((leg): leg is { match: VerdictSummary; dir: Dir; odds: number; rake: number } => leg !== null),
    [matches, selection],
  );
  const publishedIds = useMemo(
    () => new Set((recommendationsQuery.data?.snapshots ?? [])
      .map((item) => item.verdict?.id)
      .filter((id): id is string => Boolean(id))),
    [recommendationsQuery.data],
  );
  const modelCovered = legs.filter((leg) => {
    const shrunk = leg.match.model?.shrunk;
    return publishedIds.has(leg.match.id)
      && leg.match.status === "promoted"
      && Array.isArray(shrunk) && shrunk.length === 3;
  }).length;
  const hasMarketOnly = legs.some((leg) => {
    const shrunk = leg.match.model?.shrunk;
    return !publishedIds.has(leg.match.id)
      || leg.match.status !== "promoted"
      || !Array.isArray(shrunk) || shrunk.length !== 3;
  });

  const resetReport = () => {
    checkSeq.current += 1;
    setReportOpen(false);
    setReport(null);
    check.reset();
  };

  const generatePlan = () => {
    setPlanData(null);
    setPlanReviewed(false);
    plan.mutate({ stake, date }, {
      onSuccess: (data) => {
        setPlanData(data);
        setPlanReviewed(false);
      },
      onError: (error) => toast.show(errorText(error), "warning"),
    });
  };

  const autoPlanDate = useRef("");
  useEffect(() => {
    if (autoPlanDate.current === date) return;
    autoPlanDate.current = date;
    // 进入页面/切日期自动配一次；失败保留按钮重试。
    if (recommendationsQuery.isSuccess && recommendationsQuery.data.plans.length > 0) return;
    plan.mutate({ stake, date }, {
      onSuccess: (data) => {
        setPlanData(data);
        setPlanReviewed(false);
      },
      onError: (error) => toast.show(errorText(error), "warning"),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  useEffect(() => {
    if (!recommendationsQuery.isSuccess || recommendationsQuery.data.plans.length === 0) return;
    const published = recommendationsQuery.data.plans;
    setPlanData({
      date,
      candidates: published.length,
      plans: published.map((item) => ({
        label: item.label,
        risk_profile: item.riskProfile,
        legs: item.legs,
        check: item.check as unknown as ParlayCheck,
        note: item.note,
        conditions: item.conditions,
        invalidators: item.invalidators,
        review: item.review,
      })),
      message: null,
    });
    setPlanReviewed(true);
  }, [date, recommendationsQuery.data, recommendationsQuery.isSuccess]);

  const toggle = (verdict: VerdictSummary, dir: Dir) => {
    resetReport();
    // 改方向时同步移出共享腿池，避免刷新后又被旧方向覆盖。
    const stored = storeLegs.find((leg) => leg.verdictId === verdict.id);
    if (stored && stored.dir !== dir) removeStoreLeg(verdict.id);
    setSelection((prev) => {
      const next = { ...prev };
      if (next[verdict.id] === dir) {
        delete next[verdict.id];
        removeStoreLeg(verdict.id);
        return next;
      }
      if (!next[verdict.id] && Object.keys(next).length >= PARLAY_MAX_LEGS) {
        toast.show(`串关最多选 ${PARLAY_MAX_LEGS} 腿，腿越多相关性和成本越高`, "warning");
        return prev;
      }
      const sameMatch = Object.keys(next).some((id) =>
        id !== verdict.id && matches.find((m) => m.id === id)?.matchId === verdict.matchId);
      if (!next[verdict.id] && sameMatch) {
        toast.show("同一场比赛只能选一个方向", "warning");
        return prev;
      }
      next[verdict.id] = dir;
      return next;
    });
  };

  const scrollToReport = () => {
    scrollRef.current?.scrollTo({ y: Math.max(0, reportY.current - 12), animated: true });
  };

  const runCheck = () => {
    const seq = ++checkSeq.current;
    setReportOpen(true);
    setReport(null);
    pendingScroll.current = true;
    check.mutate(
      { legs: legs.map((leg) => ({ verdict_id: leg.match.id, dir: leg.dir })), stake },
      {
        onSuccess: (data) => {
          if (seq === checkSeq.current) setReport(data);
        },
        onError: (error) => {
          if (seq === checkSeq.current) toast.show(errorText(error), "warning");
        },
      },
    );
  };

  const startReport = () => {
    if (legs.length < 2) {
      toast.show("串关至少选 2 场，先再选一场", "warning");
      return;
    }
    if (reportOpen && report) {
      scrollToReport();
      return;
    }
    runCheck();
  };

  const copy = async () => {
    const text = legs
      .map((leg) => {
        const label = pickDirectionLabel(leg.match.pool, leg.dir);
        const line = leg.match.goalLine ? `（${leg.match.goalLine}）` : "";
        return `${leg.match.matchNo} ${leg.match.home} ${label}${line} @${decimalToFormat(leg.odds, oddsFormat)}（${oddsFormatLabel(oddsFormat)}）`;
      })
      .join(" + ");
    await Clipboard.setStringAsync(`${text} ×${stake}元`);
    toast.show("组合账单已复制", "success");
  };

  const modelSummary = (match: VerdictSummary) => {
    const shrunk = match.model?.shrunk;
    if (!Array.isArray(shrunk) || shrunk.length !== 3) return "模型未覆盖";
    const idx = shrunk.indexOf(Math.max(...shrunk));
    const dir = (["home", "draw", "away"] as Dir[])[idx];
    return `模型 ${DIR_LABEL[dir]} ${pct(shrunk[idx])}`;
  };
  const gateSummary = (match: VerdictSummary) =>
    (["price", "market", "model"] as const)
      .map((key) => {
        const result = match.gates[key];
        const mark = result === "pass" ? "✓" : result === "fail" ? "✕" : "○";
        return `${key === "price" ? "价" : key === "market" ? "市" : "模"}${mark}`;
      })
      .join(" ");

  return (
    <AppScreen bottom={false}>
      <AppHeader title="串关参谋" showAssistant={false} onBack={() => goBackOr(router)} />
      <ScrollView
        ref={scrollRef}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text variant="overline" color={colors.green}>串关参谋 · 帮我配</Text>
        <Text variant="display" style={styles.title}>先看组合，再自己改</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          从今日有预测的场次生成参考组合；也可以往下自己选 2–6 场做四维体检。
          当前显示：{oddsFormatLabel(oddsFormat)}。
        </Text>
        <DateStrip
          value={date}
          onChange={(next) => {
            if (next === date) return; // 重复点当前日期不应清空已选腿
            chooseDate(next);
            setSelection({});
            clearStore();
            resetReport();
            setPlanData(null);
            plan.reset();
          }}
        />

        {hasMarketOnly ? (
          <View style={styles.marketWarning}>
            <Text variant="caption" color={colors.amber}>
              含市场参考腿：整组标「未复核·仅市场参考」，不构成模型预测。
            </Text>
          </View>
        ) : null}

        <View style={styles.planBox}>
          <Text variant="captionStrong" color={colors.muted}>帮我配</Text>
          <Text variant="small" color={colors.muted}>
            从今日有预测的场次生成保守/均衡/进取参考组合；没有足够腿就不硬配。
          </Text>
          <Button
            label={plan.isPending ? "生成中…" : "生成参考组合"}
            variant="secondary"
            disabled={plan.isPending}
            onPress={generatePlan}
          />
          {planData ? <ParlayPlans data={planData} oddsFormat={oddsFormat} reviewed={planReviewed} /> : null}
        </View>

        <Text variant="captionStrong" color={colors.muted} style={styles.label}>或者自己选一场</Text>

        {streamQuery.isLoading ? (
          <CardSkeleton />
        ) : streamQuery.isError ? (
          <ErrorState message={errorText(streamQuery.error)} onRetry={() => streamQuery.refetch()} />
        ) : matches.length === 0 ? (
          <View style={styles.emptyBox}>
            <Text variant="body" color={colors.muted} style={styles.empty}>
              {date === currentTradeDateCn()
                ? "今天还没有带赔率的场次可算。可以切到昨天看真实数据，或去「今日在售」看同步状态。"
                : "这一天没有可计算的场次。"}
            </Text>
            {date === currentTradeDateCn() ? (
              <Button label="看昨天" variant="secondary" size="sm" onPress={() => chooseDate(shiftDateCn(currentTradeDateCn(), -1))} />
            ) : null}
          </View>
        ) : (
          <View style={styles.list}>
            {matches.map((match) => (
              <View key={match.id} style={styles.matchCard}>
                <View style={styles.matchHead}>
                  <View style={styles.flex}>
                    <Text variant="bodyStrong" numberOfLines={1}>
                      {match.home} <Text variant="caption" color={colors.muted}>vs</Text> {match.away}
                    </Text>
                    <Text variant="caption" color={colors.muted}>
                      {match.matchNo}{match.goalLine ? ` · 让球 ${match.goalLine}` : ""} · 抽水 {pct(match.rake)} · {match.status === "promoted" ? "三关全过" : "复核中"}
                    </Text>
                    <Text variant="caption" color={colors.muted}>
                      {modelSummary(match)} · 三闸 {gateSummary(match)}
                    </Text>
                  </View>
                  {match.pick?.dir ? (
                    <Text variant="caption" color={colors.green}>
                      已判 {pickDirectionLabel(match.pool, match.pick.dir)}
                    </Text>
                  ) : null}
                </View>
                <View style={styles.oddsRow}>
                  {(["home", "draw", "away"] as Dir[]).map((dir) => {
                    const selected = selection[match.id] === dir;
                    return (
                      <Pressable
                        key={dir}
                        onPress={() => toggle(match, dir)}
                        accessibilityRole="button"
                        accessibilityState={{ selected }}
                        accessibilityLabel={`${match.home} 对 ${match.away}，${pickDirectionLabel(match.pool, dir)}，赔率 ${match.sp[DIR_KEY[dir]]}`}
                        style={({ pressed }) => [
                          styles.oddsButton,
                          selected && styles.oddsSelected,
                          pressed && styles.pressed,
                        ]}
                      >
                        <Text variant="caption" color={selected ? colors.white : colors.muted}>
                          {match.pool === "hhad" ? "让球" : ""}{DIR_LABEL[dir]}
                        </Text>
                        <Text variant="bodyStrong" color={selected ? colors.white : colors.ink}>
                          {decimalToFormat(match.sp[DIR_KEY[dir]], oddsFormat)}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              </View>
            ))}
          </View>
        )}

        <Text variant="captionStrong" color={colors.muted} style={styles.label}>单注金额</Text>
        <Stepper
          value={stake}
          onChange={(next) => {
            setStake(next);
            resetReport();
            setPlanData(null);
            plan.reset();
          }}
          min={10}
          max={10000}
          step={10}
        />

        {reportOpen ? (
          <View
            style={styles.report}
            onLayout={(event) => {
              reportY.current = event.nativeEvent.layout.y;
              if (pendingScroll.current) {
                pendingScroll.current = false;
                requestAnimationFrame(scrollToReport);
              }
            }}
          >
            {check.isPending ? (
              <CardSkeleton />
            ) : check.isError ? (
              <ErrorState message={errorText(check.error)} onRetry={runCheck} />
            ) : report ? (
              <>
                <ParlayReport data={report} oddsFormat={oddsFormat} />
                <View style={styles.actions}>
                  <Button label="复制组合账单" variant="secondary" icon="copy-outline" onPress={copy} fullWidth />
                  <Button label="去今日在售" variant="ghost" onPress={() => router.push("/tools/on-sale")} fullWidth />
                </View>
              </>
            ) : null}
          </View>
        ) : (
          <Text variant="small" color={colors.muted} style={styles.hint}>
            {legs.length === 0
              ? "先选 2–6 场，再点底部「开始体检」。"
              : legs.length < 2
                ? "再选 1 场，底部按钮就会亮起。"
                : `已选好，${modelCovered}/${legs.length} 腿有模型；点底部「开始体检」。`}
          </Text>
        )}
      </ScrollView>

      <View style={[styles.ctaBar, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
        <View style={styles.ctaInfo}>
          <Text variant="captionStrong">已选 {legs.length} / {PARLAY_MAX_LEGS} 腿</Text>
          <Text variant="caption" color={colors.muted}>
            {legs.length < 2
              ? `至少 2 腿，还差 ${2 - legs.length} 场`
              : check.isPending
                ? "正在做四维体检…"
                : report
                  ? `${modelCovered}/${legs.length} 腿有模型`
                  : "成本 / 信息 / 模型 / 结构"}
          </Text>
        </View>
        <Button
          label={legs.length < 2 ? "再选一场" : check.isPending ? "分析中…" : report ? "查看结果" : "开始分析"}
          variant="primary"
          disabled={legs.length < 2 || check.isPending}
          onPress={startReport}
          style={styles.ctaButton}
        />
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: 120 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  list: { gap: spacing.sm, marginTop: spacing.x4 },
  matchCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.base,
    gap: spacing.sm,
  },
  matchHead: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  flex: { flex: 1 },
  oddsRow: { flexDirection: "row", gap: spacing.xs },
  oddsButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgElevated,
    alignItems: "center",
    justifyContent: "center",
    gap: 1,
  },
  oddsSelected: { backgroundColor: colors.green, borderColor: colors.green },
  pressed: { opacity: 0.7 },
  label: { marginTop: spacing.x4, marginBottom: spacing.xs },
  planBox: { gap: spacing.sm, marginTop: spacing.base, padding: spacing.base,
    borderRadius: radii.lg, borderWidth: 1, borderColor: colors.line,
    backgroundColor: colors.surface },
  warning: { marginTop: spacing.sm, lineHeight: 18 },
  actions: { marginTop: spacing.base, gap: spacing.sm },
  hint: { marginTop: spacing.base, lineHeight: 19 },
  marketWarning: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.base,
    borderRadius: radii.md,
    backgroundColor: colors.amberSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.amberLine,
  },
  report: { marginTop: spacing.x4, gap: spacing.xs },
  ctaBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  ctaInfo: { flex: 1, gap: 1 },
  ctaButton: { minWidth: 132 },
  empty: { lineHeight: 22 },
  emptyBox: { marginTop: spacing.x4, gap: spacing.base, alignItems: "flex-start" },
});
