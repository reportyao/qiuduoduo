import type { ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, layout, spacing } from "@/theme/tokens";
import { Avatar } from "./ui/Avatar";
import { IconButton } from "./ui/IconButton";
import { Text } from "./ui/Text";
import { usePersonaContent } from "@/features/personas/usePersona";

interface AppHeaderProps {
  title: string;
  subtitle?: string;
  showAssistant?: boolean;
  onAssistantPress?: () => void;
  right?: ReactNode;
  onBack?: () => void;
  backLabel?: string;
  border?: boolean;
  /** 首页把 Header 放进 ScrollView 时关掉安全区内边距，避免双倍顶部留白。 */
  insetTop?: boolean;
  /** 首页 HeaderMetrics 4 行时需要更高的头部。 */
  height?: number;
}

/**
 * 顶栏。Tab 页的 AI 实体由全局 FloatingAssistant 常驻，Header 不再重复放头像；
 * 首页 Header 放进 ScrollView，滚动时随内容走，不再置顶。
 */
export function AppHeader({
  title,
  subtitle,
  showAssistant = false,
  onAssistantPress,
  right,
  onBack,
  backLabel = "返回",
  border = true,
  insetTop = true,
  height,
}: AppHeaderProps) {
  const insets = useSafeAreaInsets();
  const { meta } = usePersonaContent();
  const top = insetTop ? insets.top : 0;

  return (
    <View
      style={[
        styles.wrap,
        { paddingTop: top, height: top + (height ?? layout.headerHeight) },
        border && styles.border,
      ]}
    >
      <View style={styles.side} pointerEvents="box-none">
        {onBack ? (
          <IconButton name="arrow-back" onPress={onBack} accessibilityLabel={backLabel} size={19} />
        ) : null}
        <View style={styles.titleWrap}>
          <Text variant="h2" numberOfLines={1}>{title}</Text>
          {subtitle ? (
            <Text variant="caption" color={colors.muted} numberOfLines={1}>
              {subtitle}
            </Text>
          ) : null}
        </View>
      </View>

      {showAssistant ? (
        <Pressable
          onPress={onAssistantPress}
          accessibilityRole="button"
          accessibilityLabel={`${meta.name}，点开助理`}
          style={styles.assistant}
        >
          <Avatar source={meta.avatar} size={42} online />
          <Text variant="caption" color={colors.muted} numberOfLines={1} style={styles.assistantName}>
            {meta.name}
          </Text>
        </Pressable>
      ) : null}

      <View style={[styles.side, styles.right]} pointerEvents="box-none">{right}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.bg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: layout.pagePadding,
    zIndex: 20,
  },
  border: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  side: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    zIndex: 2,
  },
  right: { justifyContent: "flex-end" },
  titleWrap: { flexShrink: 1, gap: 1 },
  assistant: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  assistantName: { marginTop: 1, fontSize: 12, lineHeight: 16 },
});
