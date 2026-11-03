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
}

/**
 * 固定顶栏。首页只放品牌/指标，助理形象在滚动内容里自然滚出；
 * 其他 Tab 把助理形象固定在中间，保证「每个 Tab 都有 AI 实体」。
 */
export function AppHeader({
  title,
  subtitle,
  showAssistant = true,
  onAssistantPress,
  right,
  onBack,
  backLabel = "返回",
  border = true,
}: AppHeaderProps) {
  const insets = useSafeAreaInsets();
  const { meta } = usePersonaContent();

  return (
    <View
      style={[
        styles.wrap,
        { paddingTop: insets.top, height: insets.top + layout.headerHeight },
        border && styles.border,
      ]}
    >
      <View style={styles.side}>
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

      <View style={[styles.side, styles.right]}>{right}</View>
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
  assistantName: { marginTop: 1, fontSize: 10, lineHeight: 13 },
});
