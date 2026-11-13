import { Text as RNText, type TextProps, type TextStyle } from "react-native";
import { colors, fontFamily, type as typeScale } from "@/theme/tokens";

export type TextVariant = keyof typeof typeScale;

interface AppTextProps extends TextProps {
  variant?: TextVariant;
  color?: string;
  /** 数字/哈希统一用等宽，避免跳动。 */
  mono?: boolean;
  center?: boolean;
}

export function Text({
  variant = "body",
  color = colors.ink,
  mono = false,
  center = false,
  style,
  ...rest
}: AppTextProps) {
  const scale = typeScale[variant] as TextStyle;
  const weight = Number(scale.fontWeight ?? 400);
  const family = mono
    ? fontFamily.mono
    : weight >= 600 ? fontFamily.medium : fontFamily.regular;
  return (
    <RNText
      {...rest}
      style={[
        scale,
        {
          color,
          fontFamily: family,
          ...(center ? { textAlign: "center" as const } : null),
        },
        style,
      ]}
      allowFontScaling
      maxFontSizeMultiplier={1.35}
    />
  );
}
