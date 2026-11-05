import type { ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Icon, type IconName } from "./Icon";
import { Text } from "./Text";

interface SettingsGroupProps {
  children: ReactNode;
  title?: string;
}

export function SettingsGroup({ children, title }: SettingsGroupProps) {
  return (
    <View style={styles.groupWrap}>
      {title ? (
        <Text variant="captionStrong" color={colors.muted} style={styles.groupTitle}>
          {title}
        </Text>
      ) : null}
      <View style={styles.group}>{children}</View>
    </View>
  );
}

interface SettingsRowProps {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IconName;
  onPress?: () => void;
  right?: ReactNode;
  danger?: boolean;
  last?: boolean;
  disabled?: boolean;
}

export function SettingsRow({
  title,
  subtitle,
  value,
  icon,
  onPress,
  right,
  danger = false,
  last = false,
  disabled = false,
}: SettingsRowProps) {
  const body = (
    <>
      {icon ? (
        <View style={[styles.iconWrap, danger && styles.iconDanger]}>
          <Icon name={icon} size={18} color={danger ? colors.danger : colors.muted} />
        </View>
      ) : null}
      <View style={styles.textWrap}>
        <Text variant="bodyStrong" color={danger ? colors.danger : colors.ink}>
          {title}
        </Text>
        {subtitle ? (
          <Text variant="caption" color={colors.muted} style={styles.subtitle}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right ?? (
        <>
          {value ? (
            <Text variant="small" color={colors.muted} numberOfLines={1} style={styles.value}>
              {value}
            </Text>
          ) : null}
          {onPress ? <Icon name="chevron-forward" size={16} color={colors.subtle} /> : null}
        </>
      )}
    </>
  );

  if (!onPress) {
    return <View style={[styles.row, !last && styles.border]}>{body}</View>;
  }
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityHint={subtitle}
      accessibilityState={{ disabled }}
      onPress={disabled ? undefined : onPress}
      style={({ pressed }) => [
        styles.row,
        !last && styles.border,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}
    >
      {body}
    </Pressable>
  );
}

export function KeyValueRow({
  label,
  value,
  strong = false,
  last = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
  last?: boolean;
}) {
  return (
    <View style={[styles.kv, !last && styles.border]}>
      <Text variant="small" color={colors.muted} style={styles.kvLabel}>{label}</Text>
      <Text variant={strong ? "bodyStrong" : "small"} style={styles.kvValue} selectable>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  groupWrap: { gap: spacing.sm },
  groupTitle: { marginLeft: spacing.xxs },
  group: {
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.line,
    overflow: "hidden",
  },
  row: {
    minHeight: 54,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.base,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
  },
  border: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { backgroundColor: colors.bgElevated },
  disabled: { opacity: 0.5 },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: colors.surfaceSunken,
    alignItems: "center",
    justifyContent: "center",
  },
  iconDanger: { backgroundColor: colors.dangerSoft },
  textWrap: { flex: 1, gap: 2 },
  subtitle: { lineHeight: 16 },
  value: { maxWidth: "46%" },
  kv: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.base,
    paddingVertical: spacing.base,
  },
  kvLabel: { flexShrink: 0 },
  kvValue: { flex: 1, textAlign: "right" },
});
