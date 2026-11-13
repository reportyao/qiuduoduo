import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { colors, fontFamily, radii, spacing, type } from "@/theme/tokens";
import { Icon, type IconName } from "./Icon";
import { Text } from "./Text";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  | "dangerGhost"
  | "light"
  | "darkPrimary"
  | "darkGhost";
export type ButtonSize = "md" | "sm";

interface ButtonProps {
  label: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityHint?: string;
}

const PALETTE: Record<
  ButtonVariant,
  { bg: string; pressed: string; fg: string; border: string }
> = {
  primary: { bg: colors.green, pressed: colors.greenPressed, fg: colors.white, border: colors.green },
  secondary: {
    bg: colors.surface,
    pressed: colors.bgElevated,
    fg: colors.ink,
    border: colors.lineStrong,
  },
  ghost: { bg: "transparent", pressed: colors.greenSoft, fg: colors.green, border: "transparent" },
  danger: { bg: colors.danger, pressed: colors.dangerPressed, fg: colors.white, border: colors.danger },
  dangerGhost: { bg: "transparent", pressed: colors.dangerSoft, fg: colors.danger, border: "transparent" },
  light: { bg: colors.greenSoft, pressed: colors.greenSoftStrong, fg: colors.green, border: colors.greenSoft },
  darkPrimary: {
    bg: colors.greenAccent,
    pressed: "#8CD6B8",
    fg: colors.greenDark,
    border: colors.greenAccent,
  },
  darkGhost: {
    bg: "transparent",
    pressed: "rgba(255,255,255,0.08)",
    fg: colors.inkInverse,
    border: "rgba(255,255,255,0.28)",
  },
};

export function Button({
  label,
  onPress,
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  loading = false,
  disabled = false,
  fullWidth = false,
  style,
  accessibilityHint,
}: ButtonProps) {
  const palette = PALETTE[variant];
  const height = size === "md" ? 48 : 40;
  const isDisabled = disabled || loading;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      onPress={isDisabled ? undefined : onPress}
      hitSlop={size === "sm" ? 8 : 4}
      style={({ pressed }) => [
        styles.base,
        {
          height,
          backgroundColor: pressed && !isDisabled ? palette.pressed : palette.bg,
          borderColor: palette.border,
          opacity: isDisabled ? 0.45 : 1,
        },
        fullWidth && styles.fullWidth,
        size === "sm" && styles.small,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={palette.fg} size="small" />
      ) : (
        <View style={styles.content}>
          {icon ? <Icon name={icon} size={size === "sm" ? 15 : 17} color={palette.fg} /> : null}
          <Text
            style={[
              size === "sm" ? type.smallStrong : type.bodyStrong,
              { color: palette.fg, fontFamily: fontFamily.medium },
            ]}
            numberOfLines={1}
          >
            {label}
          </Text>
          {iconRight ? <Icon name={iconRight} size={size === "sm" ? 14 : 16} color={palette.fg} /> : null}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radii.md,
    borderWidth: 1,
    paddingHorizontal: spacing.xl,
    alignItems: "center",
    justifyContent: "center",
  },
  fullWidth: { alignSelf: "stretch" },
  small: { paddingHorizontal: spacing.base, borderRadius: radii.sm },
  content: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
});
