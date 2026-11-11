import { useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { usePersonaContent } from "@/features/personas/usePersona";
import { colors, fontFamily, radii, shadows, spacing } from "@/theme/tokens";
import { Icon, Text } from "@/components/ui";

/** 首页底部的真实输入条：问题直接在这里发，回答也回到同一条对话流。 */
export function ChatComposer({
  onSend,
  sending = false,
}: {
  onSend: (text: string) => void;
  sending?: boolean;
}) {
  const { copy } = usePersonaContent();
  // 输入状态放在输入条内部：打字不再触发整页首页重渲染。
  const [value, setValue] = useState("");
  const disabled = !value.trim() || sending;
  const submit = () => {
    const text = value.trim();
    if (!text || sending) return;
    setValue("");
    onSend(text);
  };
  return (
    <View style={styles.wrap}>
      <View style={styles.bar}>
        <View style={styles.spark}>
          <Icon name="sparkles" size={15} color={colors.green} />
        </View>
        <TextInput
          value={value}
          onChangeText={setValue}
          placeholder={copy.chatPlaceholder}
          placeholderTextColor={colors.subtle}
          style={styles.input}
          multiline
          maxLength={300}
          selectionColor={colors.green}
          accessibilityLabel="向助理提问"
          editable={!sending}
        />
        <Pressable
          onPress={submit}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel="发送"
          style={({ pressed }) => [
            styles.send,
            { opacity: disabled ? 0.35 : pressed ? 0.8 : 1 },
          ]}
        >
          <Icon name="arrow-up" size={18} color={colors.white} />
        </Pressable>
      </View>
      {sending ? (
        <Text variant="caption" color={colors.subtle} style={styles.hint}>正在等助理核对数据…</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: spacing.xxl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    backgroundColor: colors.bg,
  },
  bar: {
    minHeight: 54,
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    flexDirection: "row",
    alignItems: "flex-end",
    paddingLeft: spacing.base,
    paddingRight: spacing.xs,
    paddingVertical: spacing.xs,
    gap: spacing.sm,
    ...shadows.float,
  },
  spark: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  input: {
    flex: 1,
    minHeight: 34,
    maxHeight: 110,
    paddingTop: 8,
    paddingBottom: 8,
    color: colors.ink,
    fontFamily: fontFamily.regular,
    fontSize: 14,
    lineHeight: 20,
  },
  send: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.green,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 0,
  },
  hint: { marginTop: 4, paddingLeft: spacing.base },
});
