import { Pressable, StyleSheet, View } from "react-native";
import { usePersonaContent } from "@/features/personas/usePersona";
import { colors, radii, shadows, spacing } from "@/theme/tokens";
import { Icon, Text } from "@/components/ui";

export function ChatComposer({ onPress }: { onPress: () => void }) {
  const { copy } = usePersonaContent();
  return (
    <View pointerEvents="box-none" style={styles.wrap}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel="打开 AI 助理对话"
        style={({ pressed }) => [styles.bar, pressed && styles.pressed]}
      >
        <View style={styles.spark}>
          <Icon name="sparkles" size={15} color={colors.green} />
        </View>
        <Text variant="small" color={colors.muted} style={styles.placeholder} numberOfLines={1}>
          {copy.chatPlaceholder}
        </Text>
        <View style={styles.send}>
          <Icon name="arrow-up" size={18} color={colors.white} />
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: spacing.xxl,
    right: spacing.xxl,
    bottom: spacing.sm,
  },
  bar: {
    height: 54,
    backgroundColor: colors.surface,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    flexDirection: "row",
    alignItems: "center",
    paddingLeft: spacing.base,
    paddingRight: 5,
    gap: spacing.sm,
    ...shadows.float,
  },
  pressed: { opacity: 0.9 },
  spark: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholder: { flex: 1 },
  send: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.green,
    alignItems: "center",
    justifyContent: "center",
  },
});
