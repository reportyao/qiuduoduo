import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Icon } from "@/components/ui";
import { Text } from "@/components/ui";
import { formatDate, shiftDateCn, todayCn, weekdayCn } from "@/lib/format";

interface DateNavigatorProps {
  date: string;
  onChange: (date: string) => void;
}

function dayHint(date: string): string {
  const today = todayCn();
  if (date === today) return "今天";
  if (date === shiftDateCn(today, -1)) return "昨天";
  return weekdayCn(date);
}

/** 自然日切换：左右各一天，未来日期禁用；不弹日历，避免打断浏览。 */
export function DateNavigator({ date, onChange }: DateNavigatorProps) {
  const nextDisabled = date >= todayCn();
  return (
    <View style={styles.wrap}>
      <Pressable
        onPress={() => onChange(shiftDateCn(date, -1))}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel="前一天"
        style={({ pressed }) => [styles.arrow, pressed && styles.pressed]}
      >
        <Icon name="chevron-back" size={18} color={colors.ink} />
      </Pressable>
      <View style={styles.center}>
        <Text variant="h3">{formatDate(date)}</Text>
        <Text variant="caption" color={colors.muted}>{dayHint(date)}</Text>
      </View>
      <Pressable
        onPress={() => onChange(shiftDateCn(date, 1))}
        disabled={nextDisabled}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel="后一天"
        accessibilityState={{ disabled: nextDisabled }}
        style={({ pressed }) => [
          styles.arrow,
          pressed && styles.pressed,
          nextDisabled && styles.disabled,
        ]}
      >
        <Icon name="chevron-forward" size={18} color={nextDisabled ? colors.subtle : colors.ink} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: spacing.xs,
    minHeight: 56,
    marginTop: spacing.md,
  },
  center: { alignItems: "center", gap: 0 },
  arrow: {
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { backgroundColor: colors.surfaceSunken },
  disabled: { opacity: 0.35 },
});
