import type { ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { colors, radii, shadows, spacing } from "@/theme/tokens";
import { Text } from "./Text";

interface CardProps {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  accessibilityLabel?: string;
  padded?: boolean;
  tone?: "default" | "green" | "amber" | "danger" | "dark";
}

export function Card({
  children,
  style,
  onPress,
  accessibilityLabel,
  padded = true,
  tone = "default",
}: CardProps) {
  const bg = {
    default: colors.surface,
    green: colors.greenSoft,
    amber: colors.amberSoft,
    danger: colors.dangerSoft,
    dark: colors.heroBottom,
  }[tone];
  const contentStyle = [
    styles.card,
    { backgroundColor: bg },
    padded && styles.padded,
    tone === "dark" && styles.dark,
    style,
  ];
  if (!onPress) return <View style={contentStyle}>{children}</View>;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      style={({ pressed }) => [contentStyle, pressed && { opacity: 0.9 }]}
    >
      {children}
    </Pressable>
  );
}

export function Divider({ style }: { style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.divider, style]} />;
}

interface SectionHeaderProps {
  title: string;
  eyebrow?: string;
  actionLabel?: string;
  onAction?: () => void;
  style?: StyleProp<ViewStyle>;
}

export function SectionHeader({ title, eyebrow, actionLabel, onAction, style }: SectionHeaderProps) {
  return (
    <View style={[styles.section, style]}>
      <View style={styles.sectionText}>
        {eyebrow ? <Text variant="overline" color={colors.muted}>{eyebrow}</Text> : null}
        <Text variant="h3">{title}</Text>
      </View>
      {actionLabel && onAction ? (
        <Pressable onPress={onAction} hitSlop={8} accessibilityRole="button">
          <Text variant="smallStrong" color={colors.green}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.line,
    ...shadows.card,
  },
  padded: { padding: spacing.x3 },
  dark: { borderColor: colors.heroLine },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.line },
  section: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.base,
    marginTop: spacing.x4,
    marginBottom: spacing.sm,
  },
  sectionText: { gap: 2, flex: 1 },
});
