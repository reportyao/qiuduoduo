import { useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Avatar, Button, Card, Chip, Icon, Text, useToast } from "@/components/ui";
import type { ChatCard } from "@/domain/types";
import { useChatMutation } from "@/features/assistant/queries";
import { useMemoryMutations } from "@/features/account/queries";
import { usePersonaContent } from "@/features/personas/usePersona";
import { errorText } from "@/lib/errors";
import { colors, fontFamily, layout, radii, shadows, spacing } from "@/theme/tokens";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  card?: ChatCard;
  error?: boolean;
}

const SUGGESTIONS = ["今晚买啥", "为什么不推", "复盘", "记住我的主队是曼城"];
const INTENT_LABEL: Record<string, string> = {
  buy_tonight: "今日结论",
  why_not: "死因",
  postmortem: "复盘",
  memory_write: "记忆",
  memory_query: "记忆",
  rest: "休息",
  protection: "连败保护",
  lookup_team: "球队查询",
  lookup_match: "比赛查询",
  fallback: "可以这样问",
};

export default function AssistantScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { meta, copy } = usePersonaContent();
  const chat = useChatMutation();
  const { save: saveMemory } = useMemoryMutations();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const scrollRef = useRef<ScrollView>(null);

  const send = (raw?: string) => {
    const text = (raw ?? input).trim();
    if (!text || chat.isPending) return;
    setInput("");
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", text }]);
    chat.mutate(text, {
      onSuccess: (card) => {
        setMessages((prev) => [
          ...prev,
          { id: `a-${Date.now()}`, role: "assistant", text: card.text, card },
        ]);
      },
      onError: (e) => {
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}`,
            role: "assistant",
            text: errorText(e),
            error: true,
          },
        ]);
      },
    });
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title={meta.name}
        subtitle="问今晚、问死因、问复盘"
        showAssistant={false}
        onBack={() => router.back()}
        backLabel="关闭助理"
        right={
          messages.length > 0 ? (
            <Pressable
              onPress={() => setMessages([])}
              accessibilityRole="button"
              accessibilityLabel="清空对话"
              hitSlop={8}
            >
              <Text variant="caption" color={colors.muted}>清空</Text>
            </Pressable>
          ) : null
        }
      />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={0}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.greeting}>
            <Avatar source={meta.avatar} size={36} />
            <View style={styles.greetingBubble}>
              <Text variant="small" color={colors.ink} style={styles.bubbleText}>
                {copy.chatGreeting}
              </Text>
            </View>
          </View>

          <View style={styles.chips}>
            {SUGGESTIONS.map((s) => (
              <Chip key={s} label={s} onPress={() => send(s)} />
            ))}
          </View>

          {messages.map((message) =>
            message.role === "user" ? (
              <View key={message.id} style={styles.userRow}>
                <View style={styles.userBubble}>
                  <Text variant="small" color={colors.white}>{message.text}</Text>
                </View>
              </View>
            ) : (
              <AssistantBubble
                key={message.id}
                message={message}
                onOpenVerdict={(id) => router.push({ pathname: "/verdict/[id]", params: { id } })}
                onConfirmMemory={(key, value) => {
                  saveMemory.mutate(
                    { key, value, confirm: true },
                    {
                      onSuccess: () => {
                        toast.show("已覆盖记忆", "success");
                        setMessages((prev) => [
                          ...prev,
                          { id: `m-${Date.now()}`, role: "assistant", text: `已更新：${key} = ${value}。` },
                        ]);
                      },
                      onError: (e) => toast.show(errorText(e), "error"),
                    },
                  );
                }}
              />
            ),
          )}

          {chat.isPending ? (
            <View style={styles.typing}>
              <ActivityIndicator size="small" color={colors.green} />
              <Text variant="caption" color={colors.muted}>{meta.name}正在核对数据…</Text>
            </View>
          ) : null}
          <View style={{ height: 12 }} />
        </ScrollView>

        <View style={[styles.inputBar, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder={copy.chatPlaceholder}
            placeholderTextColor={colors.subtle}
            style={styles.input}
            multiline
            maxLength={300}
            selectionColor={colors.green}
            accessibilityLabel="向助理提问"
            onSubmitEditing={() => send()}
            blurOnSubmit={false}
          />
          <Pressable
            onPress={() => send()}
            disabled={!input.trim() || chat.isPending}
            accessibilityRole="button"
            accessibilityLabel="发送"
            style={({ pressed }) => [
              styles.send,
              { opacity: !input.trim() || chat.isPending ? 0.4 : pressed ? 0.8 : 1 },
            ]}
          >
            <Icon name="arrow-up" size={19} color={colors.white} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

function AssistantBubble({
  message,
  onOpenVerdict,
  onConfirmMemory,
}: {
  message: ChatMessage;
  onOpenVerdict: (id: string) => void;
  onConfirmMemory: (key: string, value: string) => void;
}) {
  const card = message.card;
  return (
    <View style={styles.assistantRow}>
      <View style={styles.assistantBubble}>
        {card?.type ? (
          <Text variant="overline" color={colors.green}>{INTENT_LABEL[card.type] ?? "解球"}</Text>
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

        {card?.deadGate ? <Chip label={`死因：${card.deadGate}`} tone="amber" /> : null}

        {card?.conflict ? (
          <Card tone="amber" style={styles.conflict}>
            <Text variant="caption" color={colors.amber}>
              我记的是「{card.conflict.existing}」，你现在说是「{card.conflict.incoming}」。
            </Text>
            <Button
              label="确认覆盖"
              variant="secondary"
              size="sm"
              onPress={() => onConfirmMemory(card.conflict!.key, card.conflict!.incoming)}
            />
          </Card>
        ) : null}

        {card?.postmortem ? (
          <Card tone="green" style={styles.postmortem}>
            <Text variant="captionStrong" color={colors.green}>{card.postmortem.attribution?.class ?? "复盘"}</Text>
            <Text variant="caption" color={colors.muted}>{card.postmortem.attribution?.note ?? card.postmortem.whatIf}</Text>
          </Card>
        ) : null}

        {card?.verdictId ? (
          <Button
            label="看完整账"
            variant="secondary"
            size="sm"
            onPress={() => onOpenVerdict(card.verdictId!)}
            style={styles.cardButton}
          />
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.sm, paddingBottom: spacing.base },
  greeting: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  greetingBubble: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderTopLeftRadius: 6,
    padding: spacing.base,
    borderWidth: 1,
    borderColor: colors.line,
  },
  bubbleText: { lineHeight: 21 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.base, marginBottom: spacing.sm },
  userRow: { alignItems: "flex-end", marginTop: spacing.sm },
  userBubble: {
    maxWidth: "82%",
    backgroundColor: colors.green,
    borderRadius: radii.lg,
    borderBottomRightRadius: 6,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
  },
  assistantRow: { alignItems: "flex-start", marginTop: spacing.sm },
  assistantBubble: {
    maxWidth: "92%",
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderTopLeftRadius: 6,
    padding: spacing.base,
    borderWidth: 1,
    borderColor: colors.line,
    gap: spacing.xs,
  },
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
  typing: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.base },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
    backgroundColor: colors.bg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  input: {
    flex: 1,
    minHeight: 46,
    maxHeight: 110,
    backgroundColor: colors.surface,
    borderRadius: radii.xl,
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: spacing.base,
    paddingTop: 12,
    paddingBottom: 12,
    color: colors.ink,
    fontFamily: fontFamily.regular,
    fontSize: 14,
    lineHeight: 20,
  },
  send: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.green,
    alignItems: "center",
    justifyContent: "center",
    ...shadows.card,
  },
});
