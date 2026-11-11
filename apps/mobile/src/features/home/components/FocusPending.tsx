import { StyleSheet, View } from "react-native";
import { Button, Text } from "@/components/ui";
import { AssistantMessage } from "./ConversationShell";
import type { FocusTarget } from "../focusStore";
import { formatTime } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

/** 聚焦了比赛但还没有可展示判决时的对话卡片。 */
export function FocusPending({
  focus,
  onOpenVerdict,
  onWhyNot,
  onOnSale,
  onSwitch,
}: {
  focus: FocusTarget;
  onOpenVerdict: (id: string) => void;
  onWhyNot: (matchId: string) => void;
  onOnSale: () => void;
  onSwitch: () => void;
}) {
  const status =
    focus.status === "promoted" ? "三关全过"
      : focus.status === "killed" ? "未给预测"
        : focus.status === "screening" ? "复核中"
          : "在售";
  const hasVerdict = Boolean(focus.verdictId);
  return (
    <AssistantMessage>
      <Text variant="h3">{focus.home} vs {focus.away}</Text>
      <Text variant="caption" color={colors.muted}>
        {focus.matchNo} · {formatTime(focus.kickoff)} 停售 · {status}
      </Text>
      <Text variant="body" color={colors.ink} style={styles.text}>
        {hasVerdict
          ? "这场还没有完整预测可展示；数据没齐之前，不给你硬凑预测。"
          : "这场还在售，助理还没算完；先看赛程，别急着下。"}
      </Text>
      <View style={styles.actions}>
        {hasVerdict ? (
          <>
            <Button
              label="看完整预测"
              variant="primary"
              onPress={() => focus.verdictId && onOpenVerdict(focus.verdictId)}
              style={styles.action}
            />
            <Button
              label="为什么还不出"
              variant="secondary"
              onPress={() => onWhyNot(focus.matchId)}
              style={styles.action}
            />
          </>
        ) : (
          <>
            <Button label="看今日在售" variant="primary" onPress={onOnSale} style={styles.action} />
            <Button label="换一场" variant="secondary" onPress={onSwitch} style={styles.action} />
          </>
        )}
      </View>
    </AssistantMessage>
  );
}

const styles = StyleSheet.create({
  text: { marginTop: spacing.xs, lineHeight: 22 },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  action: { flex: 1 },
});
