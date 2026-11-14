import { useRef, useState } from "react";
import { goBackOr } from "@/lib/navigation";
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
import { Chip, Icon, Text, useToast } from "@/components/ui";
import { useChatMutation } from "@/features/assistant/queries";
import { ChatCardContent, type ChatMessage } from "@/features/assistant/components/ChatCardContent";
import { useFocusStore } from "@/features/home/focusStore";
import { useMemoryMutations } from "@/features/account/queries";
import { usePersonaContent } from "@/features/personas/usePersona";
import { errorText } from "@/lib/errors";
import { colors, fontFamily, layout, radii, shadows, spacing } from "@/theme/tokens";

const SUGGESTIONS = ["今日预测", "为什么不出", "复盘", "记住我的主队是曼城"];

export default function AssistantScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const { meta, copy } = usePersonaContent();
  const chat = useChatMutation();
  const focus = useFocusStore((s) => s.focus);
  const { save: saveMemory } = useMemoryMutations();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [confirmedConflicts, setConfirmedConflicts] = useState<string[]>([]);
  const scrollRef = useRef<ScrollView>(null);
  const idRef = useRef(0);
  const nextId = (prefix: string) => {
    idRef.current += 1;
    return `${prefix}-${idRef.current}`;
  };

  const send = (raw?: string) => {
    const text = (raw ?? input).trim();
    if (!text || chat.isPending) return;
    setInput("");
    setMessages((prev) => [...prev, { id: nextId("u"), role: "user", text }]);
    // 兼容尚未升级的后端：新快捷词用旧意图词发送，避免落到 fallback。
    const apiText = text === "今日预测" ? "今晚看哪场" : text;
    const wantsAnalysis = ["分析", "这场", "依据", "怎么看", "风险"].some((hint) => text.includes(hint));
    chat.mutate({ text: apiText, matchId: wantsAnalysis ? focus?.matchId : undefined }, {
      onSuccess: (card) => {
        setMessages((prev) => [
          ...prev,
          { id: nextId("a"), role: "assistant", text: card.text, card },
        ]);
      },
      onError: (e) => {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId("e"),
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
        subtitle="问预测、问依据、问复盘"
        showAssistant={false}
        onBack={() => goBackOr(router)}
        backLabel="关闭助理"
        right={
          messages.length > 0 ? (
            <Pressable
              onPress={() => {
                // 请求在飞时不允许清空，否则回调会把一条回复塞回空会话。
                if (!chat.isPending) setMessages([]);
              }}
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
          <View style={styles.greetingBubble}>
            <Text variant="small" color={colors.ink} style={styles.bubbleText}>
              {copy.chatGreeting}
            </Text>
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
                  <Text variant="small" color={colors.onGreen}>{message.text}</Text>
                </View>
              </View>
            ) : (
              <View key={message.id} style={styles.assistantBubble}>
                <ChatCardContent
                  message={message}
                  confirmed={confirmedConflicts.includes(message.id)}
                  savingMemory={saveMemory.isPending}
                  onOpenVerdict={(id) => router.push({ pathname: "/verdict/[id]", params: { id } })}
                  onConfirmMemory={(key, value) => {
                  if (saveMemory.isPending) return;
                  saveMemory.mutate(
                    { key, value, confirm: true },
                    {
                      onSuccess: () => {
                        setConfirmedConflicts((prev) =>
                          prev.includes(message.id) ? prev : [...prev, message.id],
                        );
                        toast.show("已覆盖记忆", "success");
                        setMessages((prev) => [
                          ...prev,
                          {
                            id: nextId("m"),
                            role: "assistant",
                            text: `已更新：${key} = ${value}。`,
                          },
                        ]);
                      },
                      onError: (e) => toast.show(errorText(e), "error"),
                    },
                  );
                  }}
                />
              </View>
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
            <Icon name="arrow-up" size={19} color={colors.onGreen} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.sm, paddingBottom: spacing.base },
  greetingBubble: {
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
