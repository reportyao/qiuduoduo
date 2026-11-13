import { useRef, useState } from "react";
import { Keyboard, Pressable, StyleSheet, TextInput, View } from "react-native";
import { usePersonaContent } from "@/features/personas/usePersona";
import { colors, fontFamily, layout, radii, shadows, spacing } from "@/theme/tokens";
import { Icon, Text } from "@/components/ui";

/**
 * 首页底部输入：默认收起为右下角一个图标，点开才展开输入条。
 * 发送后不自动收起，方便连续追问；点右侧收起键回到图标态。
 */
export function ChatComposer({
  onSend,
  sending = false,
}: {
  onSend: (text: string) => void;
  sending?: boolean;
}) {
  const { copy } = usePersonaContent();
  const [expanded, setExpanded] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<TextInput>(null);
  const disabled = !value.trim() || sending;

  const collapse = () => {
    Keyboard.dismiss();
    setExpanded(false);
  };
  const submit = () => {
    const text = value.trim();
    if (!text || sending) return;
    setValue("");
    onSend(text);
    setTimeout(() => inputRef.current?.focus(), 40);
  };

  if (!expanded) {
    return (
      <View style={styles.collapsedWrap}>
        <Pressable
          onPress={() => setExpanded(true)}
          accessibilityRole="button"
          accessibilityLabel="展开助理输入框"
          style={({ pressed }) => [styles.fab, pressed && styles.pressed]}
        >
          <Icon name="chatbubble-ellipses" size={24} color={colors.white} />
          <View style={styles.fabDot} />
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.bar}>
        <Pressable
          onPress={collapse}
          accessibilityRole="button"
          accessibilityLabel="收起输入框"
          hitSlop={6}
          style={styles.close}
        >
          <Icon name="chevron-down" size={20} color={colors.muted} />
        </Pressable>
        <View style={styles.spark}>
          <Icon name="sparkles" size={15} color={colors.green} />
        </View>
        <TextInput
          ref={inputRef}
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
          autoFocus
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
  collapsedWrap: {
    alignItems: "flex-end",
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  fab: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.green,
    alignItems: "center",
    justifyContent: "center",
    ...shadows.float,
  },
  pressed: { opacity: 0.82 },
  fabDot: {
    position: "absolute",
    right: 3,
    top: 3,
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.greenAccent,
    borderWidth: 2,
    borderColor: colors.bg,
  },
  wrap: {
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  bar: {
    minHeight: 54,
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    flexDirection: "row",
    alignItems: "flex-end",
    paddingLeft: spacing.sm,
    paddingRight: spacing.xs,
    paddingVertical: spacing.xs,
    gap: spacing.sm,
    ...shadows.float,
  },
  close: {
    width: 32,
    height: 34,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
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
