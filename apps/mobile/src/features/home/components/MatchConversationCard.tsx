import { memo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { MatchFocus } from "@/domain/focusAdapters";
import type { VerdictSummary } from "@/domain/types";
import { Button, Text } from "@/components/ui";
import { formatTime } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";
import type { BriefMatchOption } from "./BriefMatchPicker";
import { AssistantMessage } from "./ConversationShell";
import { FocusPanel } from "./FocusPanel";
import { VerdictMessage } from "./ConversationMessages";

/**
 * 用户点选一场后，助理在对话流里发出的比赛页卡。
 * 有判决时直接复用预测卡；没有判决也把场次、时间和入口留在对话里。
 */
export const MatchConversationCard = memo(function MatchConversationCard({
  option,
  verdict,
  focusData,
  focusLoading,
  betExists,
  onOpenVerdict,
  onOpenMatch,
  onBet,
  onWhyNot,
  onSeal,
}: {
  option: BriefMatchOption;
  verdict: VerdictSummary | null;
  focusData: MatchFocus | null | undefined;
  focusLoading: boolean;
  betExists: boolean;
  onOpenVerdict: (id: string) => void;
  onOpenMatch: (matchId: string) => void;
  onBet: (verdict: VerdictSummary) => void;
  onWhyNot: (matchId: string) => void;
  onSeal: (id: string) => void;
}) {
  const dark = Boolean(verdict
    && verdict.status === "promoted"
    && verdict.tier !== "market_reference");
  const accent = dark ? colors.greenAccent : colors.green;
  const sub = dark ? colors.mutedInverse : colors.muted;
  const head = (
    <View style={styles.head}>
      <View style={styles.headRow}>
        <Text variant="overline" color={accent}>你点的这场</Text>
        <Pressable
          onPress={() => onOpenMatch(option.matchId)}
          accessibilityRole="button"
          accessibilityLabel={`${option.home} 对 ${option.away} 比赛详情`}
          hitSlop={8}
        >
          <Text variant="captionStrong" color={accent}>比赛详情 ›</Text>
        </Pressable>
      </View>
      {!dark && focusData ? <FocusPanel focus={focusData} loading={focusLoading} /> : null}
      {!dark && focusLoading && !focusData ? (
        <Text variant="caption" color={sub}>正在核对这场的覆盖数据…</Text>
      ) : null}
    </View>
  );

  if (verdict) {
    return (
      <VerdictMessage
        verdict={verdict}
        header={head}
        betExists={betExists}
        onOpen={onOpenVerdict}
        onBet={onBet}
        onWhyNot={onWhyNot}
        onSeal={onSeal}
      />
    );
  }

  return (
    <AssistantMessage>
      {head}
      <Text variant="h3" style={styles.match}>
        {option.home} <Text variant="small" color={colors.muted}>vs</Text> {option.away}
      </Text>
      <Text variant="caption" color={colors.muted}>
        {option.matchNo} · {option.league || "联赛待同步"} · {formatTime(option.kickoff)} 停售
      </Text>
      <Text variant="body" style={styles.pendingText}>
        这场还没有已发布预测。可以先进详情看数据覆盖和未出原因，不硬凑结论。
      </Text>
      <View style={styles.actions}>
        <Button
          label="为什么不出预测"
          variant="secondary"
          onPress={() => onWhyNot(option.matchId)}
          style={styles.action}
        />
        <Button
          label="比赛详情"
          variant="primary"
          onPress={() => onOpenMatch(option.matchId)}
          style={styles.action}
        />
      </View>
    </AssistantMessage>
  );
});

const styles = StyleSheet.create({
  head: { gap: spacing.xs, marginBottom: spacing.sm },
  headRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  match: { marginTop: spacing.base },
  pendingText: { marginTop: spacing.sm, lineHeight: 21 },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.base },
  action: { flex: 1 },
});
