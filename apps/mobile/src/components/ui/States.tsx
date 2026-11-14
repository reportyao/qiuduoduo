import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Button } from "./Button";
import { Icon, type IconName } from "./Icon";
import { Text } from "./Text";

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  style?: StyleProp<ViewStyle>;
}

export function EmptyState({
  icon = "leaf-outline",
  title,
  body,
  actionLabel,
  onAction,
  secondaryLabel,
  onSecondary,
  style,
}: EmptyStateProps) {
  return (
    <View style={[styles.empty, style]}>
      <View style={styles.iconWrap}>
        <Icon name={icon} size={24} color={colors.brand} />
      </View>
      <Text variant="h3" center>{title}</Text>
      <Text variant="small" color={colors.muted} center style={styles.emptyBody}>
        {body}
      </Text>
      {actionLabel && onAction ? (
        <Button label={actionLabel} onPress={onAction} variant="primary" style={styles.emptyAction} />
      ) : null}
      {secondaryLabel && onSecondary ? (
        <Button label={secondaryLabel} onPress={onSecondary} variant="ghost" size="sm" />
      ) : null}
    </View>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}

export function ErrorState({ message, onRetry, compact = false }: ErrorStateProps) {
  return (
    <View style={[styles.error, compact && styles.errorCompact]}>
      <View style={styles.errorIcon}>
        <Icon name="cloud-offline-outline" size={20} color={colors.danger} />
      </View>
      <View style={styles.errorText}>
        <Text variant="smallStrong">暂时没连上</Text>
        <Text variant="caption" color={colors.muted} style={styles.errorMessage}>
          {message}
        </Text>
      </View>
      {onRetry ? (
        <Button label="重试" onPress={onRetry} variant="secondary" size="sm" />
      ) : null}
    </View>
  );
}

export function Skeleton({
  height = 16,
  width = "100%",
  radius = 8,
  style,
}: {
  height?: number;
  width?: number | `${number}%`;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const opacity = useRef(new Animated.Value(0.45)).current;
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return; // 前庭障碍用户：静态灰块，不循环闪烁
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.9, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.45, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity, reduced]);

  return (
    <Animated.View
      style={[
        { height, width, borderRadius: radius, backgroundColor: colors.line, opacity },
        style,
      ]}
    />
  );
}

export function CardSkeleton() {
  return (
    <View style={styles.cardSkeleton}>
      <Skeleton width="42%" height={12} />
      <Skeleton width="72%" height={26} style={{ marginTop: 16 }} />
      <Skeleton width="55%" height={14} style={{ marginTop: 12 }} />
      <Skeleton width="100%" height={44} radius={12} style={{ marginTop: 20 }} />
      <Skeleton width="100%" height={58} radius={12} style={{ marginTop: 12 }} />
    </View>
  );
}

const styles = StyleSheet.create({
  empty: {
    alignItems: "center",
    paddingHorizontal: spacing.x4,
    paddingVertical: spacing.x6,
    gap: spacing.xs,
  },
  iconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  emptyBody: { maxWidth: 300 },
  emptyAction: { marginTop: spacing.base, minWidth: 150 },
  error: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.lg,
    padding: spacing.base,
  },
  errorCompact: { paddingVertical: spacing.sm },
  errorIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.dangerSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  errorText: { flex: 1, gap: 2 },
  errorMessage: { lineHeight: 16 },
  cardSkeleton: {
    backgroundColor: colors.surface,
    borderRadius: radii.hero,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.xl,
    marginTop: spacing.base,
  },
});
