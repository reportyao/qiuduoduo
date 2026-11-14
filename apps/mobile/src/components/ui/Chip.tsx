import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "./Text";

export type ChipTone = "neutral" | "positive" | "amber" | "negative" | "dark";

interface ChipProps {
  label: string;
  tone?: ChipTone;
  selected?: boolean;
  /** 多选场景用 soft，避免一排全是深绿色实心块。 */
  selectedStyle?: "solid" | "soft";
  onPress?: () => void;
  dot?: boolean;
  style?: object;
}

const TONES: Record<ChipTone, { bg: string; fg: string; border: string }> = {
  neutral: { bg: colors.bgElevated, fg: colors.muted, border: colors.line },
  positive: { bg: colors.brandSoft, fg: colors.brand, border: colors.brandSoft },
  amber: { bg: colors.amberSoft, fg: colors.amber, border: colors.amberLine },
  negative: { bg: colors.lossSoft, fg: colors.loss, border: colors.lossSoft },
  dark: { bg: colors.whiteSoft, fg: colors.inkInverse, border: colors.whiteOverlay16 },
};

export function Chip({ label, tone = "neutral", selected = false, selectedStyle = "solid", onPress, dot = false, style }: ChipProps) {
  const palette = TONES[tone];
  const selectedBg = selectedStyle === "soft" ? colors.brandSoft : colors.brand;
  // solid 选中态同 Button primary：暗色下绿底变亮，白字改深字保证对比。
  const selectedFg = selectedStyle === "soft" ? colors.brand : colors.onBrand;
  const body = (
    <View
      style={[
        styles.chip,
        {
          backgroundColor: selected ? selectedBg : palette.bg,
          borderColor: selected ? (selectedStyle === "soft" ? colors.brandSoft : colors.brand) : palette.border,
        },
        style,
      ]}
    >
      {dot ? (
        <View
          style={[
            styles.dot,
            { backgroundColor: selected ? selectedFg : palette.fg },
          ]}
        />
      ) : null}
      <Text
        variant="captionStrong"
        color={selected ? selectedFg : palette.fg}
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
    minHeight: 32,
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  dot: { width: 5, height: 5, borderRadius: 3 },
});
