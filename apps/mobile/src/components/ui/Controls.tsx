import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Icon } from "./Icon";
import { Text } from "./Text";

interface ToggleProps {
  value: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}

export function Toggle({ value, onChange, label, disabled = false }: ToggleProps) {
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityState={{ checked: value, disabled }}
      onPress={disabled ? undefined : () => onChange(!value)}
      hitSlop={{ top: 8, bottom: 8, left: 6, right: 6 }}
      style={[
        styles.track,
        { backgroundColor: value ? colors.green : colors.lineStrong, opacity: disabled ? 0.5 : 1 },
      ]}
    >
      <View style={[styles.knob, value ? styles.knobOn : styles.knobOff]} />
    </Pressable>
  );
}

interface StepperProps {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
}

export function Stepper({
  value,
  onChange,
  min = 10,
  max = 100_000,
  step = 10,
  suffix = "元",
}: StepperProps) {
  const clamp = (next: number) => Math.max(min, Math.min(max, Math.round(next)));
  return (
    <View style={styles.stepper}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="减少金额"
        onPress={() => onChange(clamp(value - step))}
        style={styles.stepButton}
      >
        <Icon name="remove" size={18} color={colors.ink} />
      </Pressable>
      <View style={styles.stepValue}>
        <Text variant="h2">{value}</Text>
        <Text variant="caption" color={colors.muted}>{suffix}</Text>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="增加金额"
        onPress={() => onChange(clamp(value + step))}
        style={styles.stepButton}
      >
        <Icon name="add" size={18} color={colors.ink} />
      </Pressable>
    </View>
  );
}

export function ProgressBar({
  value,
  tone = "green",
  height = 6,
}: {
  value: number;
  tone?: "green" | "amber" | "danger";
  height?: number;
}) {
  const color = { green: colors.green, amber: colors.amber, danger: colors.danger }[tone];
  return (
    <View style={[styles.progressTrack, { height }]}>
      <View
        style={[
          styles.progressFill,
          { width: `${Math.max(0, Math.min(1, value)) * 100}%`, backgroundColor: color },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    width: 46,
    height: 28,
    borderRadius: 14,
    padding: 3,
    justifyContent: "center",
  },
  knob: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.white,
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 2,
    shadowOffset: { width: 0, height: 1 },
  },
  knobOn: { alignSelf: "flex-end" },
  knobOff: { alignSelf: "flex-start" },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    padding: spacing.xs,
  },
  stepButton: {
    width: 44,
    height: 44,
    borderRadius: radii.sm,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
  },
  stepValue: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: spacing.xxs,
    paddingHorizontal: spacing.base,
  },
  progressTrack: {
    width: "100%",
    backgroundColor: colors.surfaceSunken,
    borderRadius: 999,
    overflow: "hidden",
  },
  progressFill: { height: "100%", borderRadius: 999 },
});
