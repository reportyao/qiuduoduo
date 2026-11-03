import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing, type } from "@/theme/tokens";
import { Text } from "./Text";

export type ChipTone = "neutral" | "green" | "amber" | "danger" | "dark";

interface ChipProps {
  label: string;
  tone?: ChipTone;
  selected?: boolean;
  onPress?: () => void;
  dot?: boolean;
  style?: object;
}

const TONES: Record<ChipTone, { bg: string; fg: string; border: string }> = {
  neutral: { bg: colors.bgElevated, fg: colors.muted, border: colors.line },
  green: { bg: colors.greenSoft, fg: colors.green, border: colors.greenSoft },
  amber: { bg: colors.amberSoft, fg: colors.amber, border: colors.amberLine },
  danger: { bg: colors.dangerSoft, fg: colors.danger, border: colors.dangerSoft },
  dark: { bg: "rgba(255,255,255,0.08)", fg: colors.inkInverse, border: "rgba(255,255,255,0.16)" },
};

export function Chip({ label, tone = "neutral", selected = false, onPress, dot = false, style }: ChipProps) {
  const palette = TONES[tone];
  const body = (
    <View
      style={[
        styles.chip,
        {
          backgroundColor: selected ? colors.green : palette.bg,
          borderColor: selected ? colors.green : palette.border,
        },
        style,
      ]}
    >
      {dot ? (
        <View
          style={[
            styles.dot,
            { backgroundColor: selected ? colors.white : palette.fg },
          ]}
        />
      ) : null}
      <Text
        style={[type.captionStrong, { color: selected ? colors.white : palette.fg }]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </View>
  );
  if (!onPress) return body;
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      accessibilityLabel={label}
    >
      {body}
    </Pressable>
  );
}

/** 状态点 + 文字，用于「三关全过 / 复核中 / 已封存」。 */
export function StatusDot({ color, size = 6 }: { color: string; size?: number }) {
  return <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color }} />;
}

const styles = StyleSheet.create({
  chip: {
    minHeight: 28,
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  dot: { width: 5, height: 5, borderRadius: 3 },
});
