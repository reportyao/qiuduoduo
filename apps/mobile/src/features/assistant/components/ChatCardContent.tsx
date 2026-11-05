import { StyleSheet, View } from "react-native";
import type { ChatCard } from "@/domain/types";
import { Button, Card, Chip, Text } from "@/components/ui";
import { colors, radii, spacing } from "@/theme/tokens";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  card?: ChatCard;
  error?: boolean;
}

export const INTENT_LABEL: Record<string, string> = {
  buy_tonight: "今日预测",
  why_not: "未出原因",
  postmortem: "复盘",
  memory_write: "记忆",
  memory_query: "记忆",
  rest: "休息",
  protection: "连败保护",
  lookup_team: "球队查询",
  lookup_match: "比赛查询",
  fallback: "可以这样问",
};

/** 助理回复的内容层：首页内联对话和独立助理页共用，避免两套卡片逻辑漂移。 */
export function ChatCardContent({
  message,
  confirmed,
  savingMemory,
  onOpenVerdict,
  onConfirmMemory,
}: {
  message: ChatMessage;
  confirmed: boolean;
  savingMemory: boolean;
  onOpenVerdict: (id: string) => void;
  onConfirmMemory: (key: string, value: string) => void;
}) {
  const card = message.card;
  return (
    <View style={styles.content}>
      {card?.type ? (
        <Text variant="overline" color={colors.green}>{INTENT_LABEL[card.type] ?? "球多多"}</Text>
      ) : null}
      <Text
        variant="small"
        color={message.error ? colors.danger : colors.ink}
        style={styles.bubbleText}
      >
        {message.text}
      </Text>

      {card?.memories && card.memories.length > 0 ? (
        <View style={styles.inner}>
          {card.memories.map((memory) => (
            <View key={memory.key} style={styles.memoryRow}>
              <Text variant="caption" color={colors.muted}>{memory.key}</Text>
              <Text variant="captionStrong" style={styles.flex}>{memory.value}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {card?.protection ? (
        <Chip
          label={`连败 ${card.protection.streak} 场 · ${card.protection.active ? "保护中" : "未触发"}`}
          tone={card.protection.active ? "danger" : "green"}
        />
      ) : null}

      {card?.deadGate ? <Chip label={`未出原因：${card.deadGate}`} tone="amber" /> : null}

      {card?.conflict && !confirmed ? (
        <Card tone="amber" style={styles.conflict}>
          <Text variant="caption" color={colors.amber}>
            我记的是「{card.conflict.existing}」，你现在说是「{card.conflict.incoming}」。
          </Text>
          <Button
            label="确认覆盖"
            variant="secondary"
            size="sm"
            loading={savingMemory}
            disabled={savingMemory}
            onPress={() => onConfirmMemory(card.conflict!.key, card.conflict!.incoming)}
          />
        </Card>
      ) : null}

      {card?.postmortem ? (
        <Card tone="green" style={styles.postmortem}>
          <Text variant="captionStrong" color={colors.green}>
            {card.postmortem.attribution?.class ?? "复盘"}
          </Text>
          <Text variant="caption" color={colors.muted}>
            {card.postmortem.attribution?.note ?? card.postmortem.whatIf}
          </Text>
        </Card>
      ) : null}

      {card?.verdictId ? (
        <Button
          label="看完整预测"
          variant="secondary"
          size="sm"
          onPress={() => onOpenVerdict(card.verdictId!)}
          style={styles.cardButton}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.xs },
  flex: { flex: 1 },
  bubbleText: { lineHeight: 21 },
  inner: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.sm,
    padding: spacing.sm,
    gap: 3,
  },
  memoryRow: { flexDirection: "row", gap: spacing.sm },
  conflict: { padding: spacing.sm, gap: spacing.xs, borderColor: colors.amberLine },
  postmortem: { padding: spacing.sm, gap: 2 },
  cardButton: { alignSelf: "flex-start", marginTop: 2 },
});
