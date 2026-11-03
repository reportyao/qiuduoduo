import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import { colors, layout } from "@/theme/tokens";
import { Icon, type IconName } from "./Icon";

interface IconButtonProps {
  name: IconName;
  onPress?: () => void;
  accessibilityLabel: string;
  size?: number;
  color?: string;
  variant?: "plain" | "bordered" | "dark";
  style?: StyleProp<ViewStyle>;
}

export function IconButton({
  name,
  onPress,
  accessibilityLabel,
  size = 20,
  color = colors.ink,
  variant = "bordered",
  style,
}: IconButtonProps) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={6}
      style={({ pressed }) => [
        styles.base,
        variant === "bordered" && styles.bordered,
        variant === "dark" && styles.dark,
        pressed && styles.pressed,
        style,
      ]}
    >
      <Icon name={name} size={size} color={color} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    width: layout.touch,
    height: layout.touch,
    borderRadius: layout.touch / 2,
    alignItems: "center",
    justifyContent: "center",
  },
  bordered: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
  },
  dark: { backgroundColor: "rgba(255,255,255,0.10)" },
  pressed: { opacity: 0.62 },
});
