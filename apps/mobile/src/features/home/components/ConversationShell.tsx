import { useEffect, useRef } from "react";
import {
  Animated,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { formatDate, currentTradeDateCn, shiftDateCn } from "@/lib/format";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { colors, gradients, radii, spacing } from "@/theme/tokens";
import { Icon } from "@/components/ui/Icon";
import { Text } from "@/components/ui/Text";

/**
 * 聊天区的一条助理消息：不再重复头像/名字，气泡占满整行。
 * 全局悬浮头像已经是唯一的人设实体，消息区只负责内容。
 */
export function AssistantMessage({
  children,
  dark = false,
  delay = 0,
  style,
}: {
  children: React.ReactNode;
  dark?: boolean;
  delay?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const reduced = useReducedMotion();
  const enter = useRef(new Animated.Value(reduced ? 1 : 0)).current;

  useEffect(() => {
    if (reduced) {
      enter.setValue(1);
      return;
    }
    const animation = Animated.timing(enter, {
      toValue: 1,
      duration: 260,
      delay,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [delay, enter, reduced]);

  return (
    <Animated.View
      style={[
        styles.message,
        style,
        {
          opacity: enter,
          transform: [
            { translateY: enter.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) },
          ],
        },
      ]}
    >
      {dark ? (
        <LinearGradient
          colors={gradients.verdict}
          start={{ x: 0.1, y: 0 }}
          end={{ x: 0.9, y: 1 }}
          style={[styles.bubble, styles.bubbleDark]}
        >
          {children}
        </LinearGradient>
      ) : (
        <View style={[styles.bubble, styles.bubbleLight]}>{children}</View>
      )}
    </Animated.View>
  );
}

/** 聊天里的日期分隔：‹ 今天 · 11月4日 ›，左右切竞彩日。 */
export function ConversationDate({
  value,
  onChange,
}: {
  value: string;
  onChange: (date: string) => void;
}) {
  const today = currentTradeDateCn();
  return (
    <View style={styles.dateRow}>
      <Pressable
        onPress={() => onChange(shiftDateCn(value, -1))}
        accessibilityRole="button"
        accessibilityLabel="上一个竞彩日"
        hitSlop={10}
        style={styles.dateArrow}
      >
        <Icon name="chevron-back" size={16} color={colors.subtle} />
      </Pressable>
      <View style={styles.datePill}>
        <Text variant="caption" color={colors.subtle}>竞彩日</Text>
        <Text variant="captionStrong" color={colors.muted}> · {formatDate(value)}</Text>
      </View>
      <Pressable
        onPress={() => onChange(shiftDateCn(value, 1))}
        disabled={value >= today}
        accessibilityRole="button"
        accessibilityLabel="下一个竞彩日"
        hitSlop={10}
        style={[styles.dateArrow, value >= today && styles.disabled]}
      >
        <Icon name="chevron-forward" size={16} color={colors.subtle} />
      </Pressable>
    </View>
  );
}

export function QuickReply({
  label,
  onPress,
  style,
}: {
  label: string;
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={4}
      style={({ pressed }) => [styles.quick, style, pressed && styles.quickPressed]}
    >
      <Text variant="captionStrong" color={colors.brand}>{label}</Text>
    </Pressable>
  );
}

export function MiniStat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <View style={styles.stat}>
      <Text variant="h3" color={accent ? colors.brand : colors.ink}>{value}</Text>
      <Text variant="caption" color={colors.subtle}>{label}</Text>
    </View>
  );
}

/** 助理正在算账的“输入中”状态。 */
export function AssistantTyping({ text }: { text: string }) {
  const reduced = useReducedMotion();
  const pulse = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 520, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.35, duration: 520, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, reduced]);
  return (
    <AssistantMessage>
      <View style={styles.typing}>
        <Text variant="small" color={colors.muted}>{text}</Text>
        <Animated.View style={{ opacity: reduced ? 1 : pulse, flexDirection: "row", gap: 3 }}>
          <View style={styles.dot} />
          <View style={styles.dot} />
          <View style={styles.dot} />
        </Animated.View>
      </View>
    </AssistantMessage>
  );
}

const styles = StyleSheet.create({
  message: { marginTop: spacing.base },
  bubble: { width: "100%", borderRadius: radii.card, padding: spacing.x3 },
  bubbleLight: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
  },
  bubbleDark: { borderWidth: 1, borderColor: colors.heroLine },
  dateRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingVertical: spacing.md,
  },
  dateArrow: { width: 28, height: 28, alignItems: "center", justifyContent: "center" },
  disabled: { opacity: 0.28 },
  datePill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceSunken,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.lg,
    paddingVertical: 6,
  },
  quick: {
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.xs,
    paddingVertical: 6,
    minHeight: 34,
    alignItems: "center",
    justifyContent: "center",
  },
  quickPressed: { opacity: 0.75 },
  stat: { flex: 1, gap: 1 },
  typing: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  dot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: colors.brand },
});
