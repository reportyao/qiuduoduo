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
  return (
    <RNText
      {...rest}
      style={[
        scale,
        {
          color,
          fontFamily: mono ? fontFamily.mono : fontFamily.regular,
          ...(center ? { textAlign: "center" as const } : null),
        },
        style,
      ]}
      allowFontScaling
      maxFontSizeMultiplier={1.35}
    />
  );
}
