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
  { bg: string; pressed: string; fg: string; border: string; ripple: string }
> = {
  primary: { bg: colors.brand, pressed: colors.brandPressed, fg: colors.onBrand, border: colors.brand, ripple: colors.whiteSoft },
  secondary: {
    bg: colors.surface,
    pressed: colors.bgElevated,
    fg: colors.ink,
    border: colors.lineStrong,
    ripple: colors.inkOverlay8,
  },
  ghost: { bg: "transparent", pressed: colors.brandSoft, fg: colors.brand, border: "transparent", ripple: colors.inkOverlay8 },
  // danger 实心底不用 colors.danger：暗色下它变亮（文字色语义），白字对比不足。
  danger: { bg: colors.dangerSolid, pressed: colors.dangerPressed, fg: colors.white, border: colors.dangerSolid, ripple: colors.whiteSoft },
  dangerGhost: { bg: "transparent", pressed: colors.dangerSoft, fg: colors.danger, border: "transparent", ripple: colors.inkOverlay8 },
  light: { bg: colors.brandSoft, pressed: colors.brandSoftStrong, fg: colors.brand, border: colors.brandSoft, ripple: colors.inkOverlay8 },
  darkPrimary: {
    bg: colors.brandAccent,
    pressed: colors.brandHighlight,
    fg: colors.brandDeep,
    border: colors.brandAccent,
    ripple: colors.inkOverlay8,
  },
  darkGhost: {
    bg: "transparent",
    pressed: colors.whiteSoft,
    fg: colors.inkInverse,
    border: colors.whiteLine,
    ripple: colors.whiteSoft,
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
      android_ripple={{ color: palette.ripple, borderless: false }}
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
    // ripple 被圆角裁剪必需；Button 无阴影，overflow 不影响其他效果。
    overflow: "hidden",
  },
  fullWidth: { alignSelf: "stretch" },
  small: { paddingHorizontal: spacing.base, borderRadius: radii.sm },
  content: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
});
