import { memo, type ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type {
  AvoidItem,
  PostmortemSummary,
  RestDay,
  StreamResponse,
  VerdictSummary,
} from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";
import { formatTime, pct, pickDirectionLabel } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Button, StatusDot, Text } from "@/components/ui";
import { gateTone } from "@/features/verdict/components/Gates";
import { ProbabilityBar } from "@/features/verdict/components/Probability";
import { SealLine } from "@/features/verdict/components/Seal";
import {
  AssistantMessage,
  MiniStat,
  QuickReply,
} from "./ConversationShell";
import { BriefMatchPicker, type BriefMatchOption } from "./BriefMatchPicker";

function verdictStatus(verdict: VerdictSummary): { label: string; color: string } {
  if (verdict.tier === "avoid" || verdict.status === "killed") {
    return { label: "回避", color: colors.danger };
  }
  if (verdict.status === "promoted") return { label: "预测", color: colors.greenAccent };
  return { label: "预测", color: colors.green };
}

/**
 * 首页开场：助理先开口，把今天的复核结果、口径和下一步动作一次说清。
 * 数据口径不随人设变化，只有语气跟着人设走。
 */
export function AssistantBrief({
  stream,
  dayLabel,
  publishedCount,
  publishedReady,
  recordText,
  onsaleCount,
  onsaleLabel,
  options,
  optionsTotal,
  expanded,
  onSelectOption,
  onExpandAll,
  onPicker,
  onOnSale,
  onParlay,
  onWhyNot,
  onData,
}: {
  stream: StreamResponse;
  dayLabel: string;
  publishedCount: number;
  publishedReady: boolean;
  recordText?: string | null;
  onsaleCount: number;
  onsaleLabel: string;
  options: BriefMatchOption[];
  optionsTotal: number;
  expanded: boolean;
  onSelectOption: (option: BriefMatchOption) => void;
  onExpandAll: () => void;
  onPicker: () => void;
  onOnSale: () => void;
  onParlay: () => void;
  onWhyNot: () => void;
  onData: () => void;
}) {
  const { copy } = usePersonaContent();
  const { stats } = stream;
  // 三关全过 + 复核中 + 已砍 = 当日复核；被砍场不混进「等数据」。
  const killed = Math.max(0, stats.total - stats.promoted - stats.screening);
  return (
    <AssistantMessage>
      {recordText ? (
        <Text variant="body" style={styles.lead}>{recordText}</Text>
      ) : null}
      <Text variant="body" style={styles.lead}>
        {copy.conversationOpen(dayLabel, stats.total, stats.promoted, publishedCount, stats.screening, killed)}
      </Text>

      <View style={styles.statRow}>
        <MiniStat label={dayLabel === "今天" ? "今日扫描" : "当日扫描"} value={String(stats.total)} />
        <View style={styles.statLine} />
        <MiniStat label="预测" value={String(stats.promoted)} />
        <View style={styles.statLine} />
        <MiniStat label="已发布" value={publishedReady ? String(publishedCount) : "—"} accent />
        <View style={styles.statLine} />
        <MiniStat label={onsaleLabel} value={String(onsaleCount)} />
      </View>

      {publishedReady && publishedCount === 0 ? (
        <Text variant="caption" color={colors.green}>点下方场次查看今日预测。</Text>
      ) : null}

      <Pressable
        onPress={onData}
        accessibilityRole="button"
        accessibilityLabel="查看数据状态"
        hitSlop={6}
        style={styles.dataLink}
      >
        <StatusDot color={colors.green} />
        <Text variant="caption" color={colors.muted} style={styles.flex} numberOfLines={1}>
          预测 · 阵容 · 市场
        </Text>
        <Text variant="caption" color={colors.green}>数据状态 ›</Text>
      </Pressable>

      <BriefMatchPicker
        options={options}
        total={optionsTotal}
        expanded={expanded}
        onSelect={onSelectOption}
        onExpandAll={onExpandAll}
      />

      <View style={styles.quickRow}>
        <QuickReply label="今日在售" onPress={onOnSale} style={styles.quickItem} />
        <QuickReply label="选一场预测" onPress={onPicker} style={styles.quickItem} />
        <QuickReply label="为什么不出预测" onPress={onWhyNot} style={styles.quickItem} />
        <QuickReply label="串关参谋" onPress={onParlay} style={styles.quickItem} />
      </View>
    </AssistantMessage>
  );
}

/** 一条已发布预测：先给方向与概率，再给依据和成本。 */
export const VerdictMessage = memo(function VerdictMessage({
  verdict,
  betExists = false,
  delay = 0,
  hero = false,
  onOpen,
  onBet,
  onWhyNot,
  onSeal,
  onParlay,
  header,
}: {
  verdict: VerdictSummary;
  betExists?: boolean;
  delay?: number;
  hero?: boolean;
  onOpen: (id: string) => void;
  onBet?: (verdict: VerdictSummary) => void;
  onWhyNot?: (matchId: string) => void;
  onSeal?: (id: string) => void;
  onParlay?: () => void;
  header?: ReactNode;
}) {
  const { copy } = usePersonaContent();
  const dark = verdict.status === "promoted";
  const status = verdictStatus(verdict);
  const marketKey = (["home", "draw", "away"] as const).reduce(
    (best, key) => verdict.probs[key] > verdict.probs[best] ? key : best, "home");
  const marketDir = marketKey === "home" ? "主胜" : marketKey === "draw" ? "平局" : "客胜";
  const pickLabel = verdict.pick?.dir
    ? pickDirectionLabel(verdict.pool, verdict.pick.dir)
    : pickDirectionLabel(verdict.pool, marketDir);
  const pickProb = verdict.pick?.prob ?? verdict.probs[marketKey];
  const summary = `${pickLabel}，预测概率 ${pickProb != null ? pct(pickProb) : "—"}。抽水 ${pct(verdict.rake)}，阈值 ${pct(verdict.rakeThreshold)}。`;

  const fg = dark ? colors.inkInverse : colors.ink;
  const sub = dark ? colors.mutedInverse : colors.muted;

  return (
    <AssistantMessage dark={dark} delay={delay}>
      {header}
      {hero ? (
        <Text variant="overline" color={dark ? colors.greenAccent : colors.green}>
          {copy.feedTitle}
        </Text>
      ) : null}
      <View style={styles.msgHead}>
        <View style={styles.statusRow}>
          <StatusDot color={dark ? colors.greenAccent : status.color} />
          <Text variant="captionStrong" color={dark ? colors.greenAccent : status.color}>
            {status.label}
          </Text>
        </View>
        <Text variant="caption" color={sub}>
          {verdict.matchNo} · {formatTime(verdict.kickoff)} 停售
        </Text>
      </View>

      <Pressable
        onPress={() => onOpen(verdict.id)}
        accessibilityRole="button"
        accessibilityLabel={`${verdict.home} 对 ${verdict.away}，查看完整预测`}
        hitSlop={4}
      >
        <Text variant="h3" color={fg} style={styles.match}>
          {verdict.home} <Text variant="small" color={sub}>vs</Text> {verdict.away}
        </Text>
        <Text variant="caption" color={sub}>
          {verdict.league || "联赛待同步"} ·{" "}
          {verdict.pool === "hhad" ? `让球 ${verdict.goalLine ?? ""}` : "胜平负"}
        </Text>
      </Pressable>

      <View style={styles.pickRow}>
        <View style={styles.pickLeft}>
          <Text variant="caption" color={sub}>预测</Text>
          <Text variant="h2" color={fg}>{pickLabel}</Text>
        </View>
        <View style={styles.pickRight}>
          <Text variant="metric" color={fg}>{pickProb != null ? pct(pickProb) : "—"}</Text>
          <Text variant="caption" color={sub}>
            {pickProb != null ? "预测概率" : "概率待定"}
          </Text>
        </View>
      </View>

      <Text variant="body" color={fg} style={styles.summary}>{summary}</Text>

      <ProbabilityBar probs={verdict.probs} dark={dark} pool={verdict.pool} />

      {verdict.snapshotId ? (
        <View style={styles.recommendation}>
          <View style={styles.recommendationHead}>
            <Text variant="overline" color={dark ? colors.greenAccent : colors.green}>
              已发布预测
            </Text>
            {verdict.review ? (
              <Text variant="caption" color={verdict.review.status === "passed" ? colors.green : colors.amber}>
                {verdict.review.llmDegraded ? "规则复核" : "AI 复核"} · {verdict.review.status === "passed" ? "通过" : "待修"}
              </Text>
            ) : null}
          </View>
          {verdict.direction ? (
            <Text variant="small" color={sub}>
              预测方向：{verdict.direction}
              {verdict.confidence != null ? ` · 置信度 ${pct(verdict.confidence)}` : ""}
              {verdict.probLow != null && verdict.probHigh != null
                ? ` · 参考区间 ${pct(verdict.probLow)}–${pct(verdict.probHigh)}`
                : verdict.intervalStatus === "accumulating" ? " · 区间样本积累中" : ""}
            </Text>
          ) : null}
          {(verdict.conditions ?? []).slice(0, 2).map((line) => (
            <Text key={`condition-${line}`} variant="caption" color={sub} style={styles.recommendationLine}>
              · 成立条件：{line}
            </Text>
          ))}
          {(verdict.invalidators ?? []).slice(0, 2).map((line) => (
            <Text key={`invalidator-${line}`} variant="caption" color={sub} style={styles.recommendationLine}>
              · 失效条件：{line}
            </Text>
          ))}
        </View>
      ) : null}

      <View style={styles.rakeRow}>
        <Text variant="caption" color={sub}>
          抽水 {pct(verdict.rake)} · 阈值 {pct(verdict.rakeThreshold)}
        </Text>
      </View>

      <View style={styles.actions}>
        {dark ? (
          <>
            <Button
              label={betExists ? copy.bought : copy.buy}
              variant="darkPrimary"
              onPress={() => onBet?.(verdict)}
              disabled={betExists}
              style={styles.action}
            />
            <Button
              label={copy.detail}
              variant="darkGhost"
              onPress={() => onOpen(verdict.id)}
              style={styles.action}
            />
          </>
        ) : (
          <>
            <Button
              label="看依据"
              variant="secondary"
              onPress={() => onWhyNot?.(verdict.matchId)}
              style={styles.action}
            />
            <Button
              label={copy.detail}
              variant="primary"
              onPress={() => onOpen(verdict.id)}
              style={styles.action}
            />
          </>
        )}
      </View>

      {hero && onParlay ? (
        <Pressable onPress={onParlay} accessibilityRole="button" hitSlop={8}>
          <Text variant="captionStrong" color={dark ? colors.greenAccent : colors.green}>
            看今日组合 ›
          </Text>
        </Pressable>
      ) : null}

      <SealLine hash={verdict.hash} sealed={verdict.sealed} dark={dark} onPress={() => onSeal?.(verdict.id)} />
    </AssistantMessage>
  );
});

/** 不推的场次也用消息说，不藏死因。 */
export function AvoidMessage({
  items,
  onOpen,
}: {
  items: AvoidItem[];
  onOpen: (matchId: string) => void;
}) {
  const { copy } = usePersonaContent();
  if (items.length === 0) return null;
  return (
    <AssistantMessage>
      <Text variant="body" style={styles.lead}>{copy.avoidLead}</Text>
      <View style={styles.list}>
        {items.map((item, index) => {
          const tone = gateTone(item.gate === "price" || item.gate === "market" || item.gate === "model" ? "fail" : "unknown");
          return (
            <Pressable
              key={item.verdictId}
              onPress={() => onOpen(item.matchId)}
              accessibilityRole="button"
              accessibilityLabel={`${item.home} 对 ${item.away}，${item.why}`}
              style={({ pressed }) => [
                styles.listRow,
                index < items.length - 1 && styles.rowLine,
                pressed && styles.pressed,
              ]}
            >
              <View style={[styles.gateDot, { backgroundColor: tone.color }]} />
              <View style={styles.flex}>
                <Text variant="smallStrong" numberOfLines={1}>
                  {item.home} <Text variant="caption" color={colors.muted}>vs</Text> {item.away}
                </Text>
                <Text variant="caption" color={colors.muted} numberOfLines={1}>{item.why}</Text>
              </View>
              <Text variant="caption" color={tone.color}>
                {item.gate === "price" ? "价闸" : item.gate === "market" ? "市闸" : "模闸"}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </AssistantMessage>
  );
}

export function PostmortemMessage({
  items,
  onOpen,
}: {
  items: PostmortemSummary[];
  onOpen: (verdictId: string) => void;
}) {
  const { copy } = usePersonaContent();
  if (items.length === 0) return null;
  return (
    <AssistantMessage>
      <Text variant="body" style={styles.lead}>{copy.postmortemLead}</Text>
      <View style={styles.list}>
        {items.map((item, index) => (
          <Pressable
            key={item.verdictId}
            onPress={() => onOpen(item.verdictId)}
            accessibilityRole="button"
            accessibilityLabel={`${item.match} 复盘`}
            style={({ pressed }) => [
              styles.listRow,
              index < items.length - 1 && styles.rowLine,
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.flex}>
              <Text variant="smallStrong">{item.match}</Text>
              <Text variant="caption" color={colors.muted}>
                {item.resultScore ?? "待结算"} · {item.attribution ?? "未归因"}
              </Text>
            </View>
            <Text
              variant="captionStrong"
              color={item.settled === "win" ? colors.green : item.settled === "lose" ? colors.danger : colors.muted}
            >
              {item.settled === "win" ? "✓ 中" : item.settled === "lose" ? "× 未中" : "待定"}
            </Text>
          </Pressable>
        ))}
      </View>
    </AssistantMessage>
  );
}

/** 未采纳复盘：当时看过、没有记注的已结算场次。 */
export function UnattendedMessage({
  items,
  onOpen,
}: {
  items: PostmortemSummary[];
  onOpen: (verdictId: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <AssistantMessage>
      <Text variant="overline" color={colors.green}>你当时看过</Text>
      <Text variant="small" color={colors.muted} style={styles.paragraph}>
        这些场次你打开过、但没有记注。赛后结果如下，只作复盘，不追损。
      </Text>
      <View style={styles.list}>
        {items.map((item, index) => (
          <Pressable
            key={item.verdictId}
            onPress={() => onOpen(item.verdictId)}
            accessibilityRole="button"
            accessibilityLabel={`${item.match} 未采纳复盘`}
            style={({ pressed }) => [
              styles.listRow,
              index < items.length - 1 && styles.rowLine,
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.flex}>
              <Text variant="smallStrong">{item.match}</Text>
              <Text variant="caption" color={colors.muted}>
                {item.resultScore ?? "待结算"} · {item.attribution ?? "未归因"}
              </Text>
            </View>
            <Text
              variant="captionStrong"
              color={item.settled === "win" ? colors.green : item.settled === "lose" ? colors.danger : colors.muted}
            >
              {item.settled === "win" ? "✓ 中" : item.settled === "lose" ? "× 未中" : "待定"}
            </Text>
          </Pressable>
        ))}
      </View>
    </AssistantMessage>
  );
}

export function RestMessage({
  rest,
  title,
  onOpenLedger,
}: {
  rest: RestDay;
  /** 看历史日期时用日期标题，避免把任何一天都写成“今天”。 */
  title?: string;
  onOpenLedger: () => void;
}) {
  const { copy } = usePersonaContent();
  return (
    <AssistantMessage>
      <Text variant="h3">{title ?? copy.restTitle}</Text>
      <Text variant="small" color={colors.muted} style={styles.paragraph}>{copy.restBody}</Text>
      {rest.course.title ? (
        <View style={styles.lesson}>
          <Text variant="captionStrong" color={colors.green}>
            {rest.course.minutes || 2} 分钟 · {rest.course.title}
          </Text>
          <Text variant="small" style={styles.paragraph}>{rest.course.body}</Text>
        </View>
      ) : null}
      <Button label="看公开账本" variant="secondary" size="sm" onPress={onOpenLedger} style={styles.selfStart} />
    </AssistantMessage>
  );
}

export function EmptyMessage({
  title,
  body,
  secondaryLabel,
  onSecondary,
  onOnSale,
}: {
  title: string;
  body: string;
  secondaryLabel: string;
  onSecondary: () => void;
  onOnSale: () => void;
}) {
  return (
    <AssistantMessage>
      <Text variant="h3">{title}</Text>
      <Text variant="small" color={colors.muted} style={styles.paragraph}>{body}</Text>
      <View style={styles.actions}>
        <Button label={secondaryLabel} variant="secondary" size="sm" onPress={onSecondary} style={styles.action} />
        <Button label="今日在售" variant="primary" size="sm" onPress={onOnSale} style={styles.action} />
      </View>
    </AssistantMessage>
  );
}

export function ErrorMessage({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <AssistantMessage>
      <Text variant="bodyStrong">这条没发出去</Text>
      <Text variant="small" color={colors.muted} style={styles.paragraph}>{message}</Text>
      <Button label="重试" variant="secondary" size="sm" onPress={onRetry} style={styles.selfStart} />
    </AssistantMessage>
  );
}

export function LoadMore({
  loading,
  onPress,
}: {
  loading: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={loading}
      accessibilityRole="button"
      accessibilityLabel="加载更多预测"
      style={({ pressed }) => [styles.more, pressed && styles.pressed, loading && styles.disabled]}
    >
      <Text variant="caption" color={colors.muted} center>
        {loading ? "正在加载…" : "↑ 加载更多预测"}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  lead: { lineHeight: 23 },
  statRow: {
    flexDirection: "row",
    alignItems: "stretch",
    marginTop: spacing.base,
    paddingTop: spacing.base,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  statLine: { width: StyleSheet.hairlineWidth, backgroundColor: colors.line, marginHorizontal: spacing.base },
  publishEmpty: { marginTop: spacing.base, paddingTop: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line, gap: 3 },
  publishNote: { lineHeight: 17 },
  dataLink: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: spacing.base,
    paddingTop: spacing.sm,
  },
  quickRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: spacing.xs,
    marginTop: spacing.base,
  },
  quickItem: { width: "48%" },
  msgHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  match: { marginTop: spacing.sm },
  pickRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.base,
    marginTop: spacing.base,
  },
  pickLeft: { flex: 1, gap: 2 },
  pickRight: { alignItems: "flex-end", gap: 0 },
  recommendation: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    gap: 3,
  },
  recommendationHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  recommendationLine: { lineHeight: 18 },
  summary: { marginVertical: spacing.base, lineHeight: 22 },
  gateWrap: { marginTop: spacing.base },
  rakeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.base },
  action: { flex: 1 },
  list: { marginTop: spacing.sm },
  listRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    minHeight: 48,
  },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { opacity: 0.7 },
  gateDot: { width: 7, height: 7, borderRadius: 4 },
  paragraph: { lineHeight: 20, marginTop: 2 },
  lesson: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    padding: spacing.base,
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  selfStart: { alignSelf: "flex-start", marginTop: spacing.base },
  more: { paddingVertical: spacing.lg, marginTop: spacing.sm },
  disabled: { opacity: 0.5 },
});
