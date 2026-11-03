import { useEffect, useMemo, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
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
import { useStreamQuery } from "@/features/home/queries";
import { useOddsFormat } from "@/features/preferences/prefsStore";
import { DateStrip } from "@/features/home/components/HomeSections";
import { parlayMath } from "@/features/tools/calc";
import { FormulaNote, ResultPanel, ResultRow } from "@/features/tools/ToolLayout";
import type { VerdictSummary } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { currentTradeDateCn, decimalToFormat, money, oddsFormatLabel, pct, pickDirectionLabel, shiftDateCn } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Dir = "home" | "draw" | "away";
type Selection = Record<string, Dir>;

const DIR_LABEL: Record<Dir, string> = { home: "主胜", draw: "平", away: "客胜" };
const DIR_KEY: Record<Dir, "h" | "d" | "a"> = { home: "h", draw: "d", away: "a" };

export default function ParlayToolScreen() {
  const router = useRouter();
  const toast = useToast();
  const oddsFormat = useOddsFormat();
  const [selection, setSelection] = useState<Selection>({});
  const [stake, setStake] = useState(100);
  const [date, setDate] = useState(currentTradeDateCn());
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
  const stream = streamQuery.data?.pages[0];

  const matches = useMemo(
    () => (stream?.verdicts ?? []).filter(
      (v) => v.rake != null && v.sp.h > 1 && v.sp.d > 1 && v.sp.a > 1,
    ).slice(0, 12),
    [stream],
  );
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
  const result = legs.length > 0 ? parlayMath(legs.map((leg) => ({ odds: leg.odds, rake: leg.rake })), stake) : null;
  const hasPendingLeg = legs.some((leg) => leg.match.status !== "promoted");

  const toggle = (verdict: VerdictSummary, dir: Dir) => {
    setSelection((prev) => {
      const next = { ...prev };
      if (next[verdict.id] === dir) {
        delete next[verdict.id];
        return next;
      }
      if (!next[verdict.id] && Object.keys(next).length >= 4) {
        toast.show("串关最多选 4 腿，腿越多越难算清", "warning");
        return prev;
      }
      next[verdict.id] = dir;
      return next;
    });
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

  return (
    <AppScreen bottom={false}>
      <AppHeader title="串关体检" showAssistant={false} onBack={() => goBackOr(router)} />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text variant="overline" color={colors.green}>串关 · 本地计算器</Text>
        <Text variant="display" style={styles.title}>别让串关把账搅浑。</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          选 2–4 场，自己选方向。工具会算组合赔率、按市场概率的期望返还，以及每一腿的抽水成本。
          当前显示：{oddsFormatLabel(oddsFormat)}。
        </Text>
        <DateStrip
          value={date}
          onChange={(next) => {
            if (next === date) return; // 重复点当前日期不应清空已选腿
            chooseDate(next);
            setSelection({});
          }}
        />

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
                          {DIR_LABEL[dir]}
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
        <Stepper value={stake} onChange={setStake} min={10} max={10000} step={10} />

        {result ? (
          <>
            <ResultPanel title={`${legs.length} 腿组合 · 本金 ${money(stake)}`}>
              <ResultRow label="组合赔率" value={`${decimalToFormat(result.comboOdds, oddsFormat)}（${oddsFormatLabel(oddsFormat)}）`} strong />
              <ResultRow label="组合隐含胜率" value={pct(result.impliedProbability, 2)} />
              <ResultRow label="理论返还率" value={pct(result.theoreticalReturnRate, 2)} tone="green" />
              <ResultRow label="期望返还" value={money(result.expectedReturn, 2)} strong tone={result.expectedReturn >= stake ? "green" : "danger"} />
              <ResultRow label="期望损耗" value={money(result.expectedLoss, 2)} tone="danger" />
            </ResultPanel>
            <FormulaNote>
              组合赔率 = Π 单腿赔率；组合隐含胜率 = 1 / 组合赔率；
              理论返还率 = Π(1 − 单腿抽水)；期望返还 = 本金 × 理论返还率。
              这是按市场概率的数学期望，不是真实命中率。
            </FormulaNote>
            {hasPendingLeg ? (
              <Text variant="small" color={colors.amber} style={styles.warning}>
                你选了复核中的场次。它们的模型置信还没齐，组合期望只代表官方赔率，不代表已过三关。
              </Text>
            ) : null}
            {legs.length >= 4 ? (
              <Text variant="small" color={colors.amber} style={styles.warning}>
                4 腿组合的方差很高：单腿 60% 的判断，四腿全中只有约 13%。这是结构，不是运气。
              </Text>
            ) : null}
            <View style={styles.actions}>
              <Button label="复制组合账单" variant="secondary" icon="copy-outline" onPress={copy} fullWidth />
              <Button label="去今日在售" variant="ghost" onPress={() => router.push("/tools/on-sale")} fullWidth />
            </View>
          </>
        ) : (
          <Text variant="small" color={colors.muted} style={styles.hint}>
            至少选 1 腿才会出现结果。建议从 2–3 腿开始。
          </Text>
        )}
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
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
  warning: { marginTop: spacing.sm, lineHeight: 18 },
  actions: { marginTop: spacing.base, gap: spacing.sm },
  hint: { marginTop: spacing.base },
  empty: { lineHeight: 22 },
  emptyBox: { marginTop: spacing.x4, gap: spacing.base, alignItems: "flex-start" },
});
