import Ionicons from "@expo/vector-icons/Ionicons";
import type { ComponentProps } from "react";
import type { StyleProp, TextStyle } from "react-native";
import { colors } from "@/theme/tokens";

export type IconName = ComponentProps<typeof Ionicons>["name"];

interface IconProps {
  name: IconName;
  size?: number;
  color?: string;
  style?: StyleProp<TextStyle>;
}

/** 全局线性图标入口：统一用 Ionicons outline，避免各页面混用 emoji/填充图标。 */
export function Icon({ name, size = 20, color = colors.ink, style }: IconProps) {
  return <Ionicons name={name} size={size} color={color} style={style} />;
}
