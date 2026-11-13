import { useEffect, useState } from "react";
import { Keyboard, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Text } from "@/components/ui/Text";
import { colors, layout } from "@/theme/tokens";

const META: Record<string, { label: string; icon: IconName; activeIcon: IconName }> = {
  index: { label: "助理", icon: "chatbubbles-outline", activeIcon: "chatbubbles" },
  matches: { label: "比赛", icon: "football-outline", activeIcon: "football" },
  plans: { label: "计划", icon: "layers-outline", activeIcon: "layers" },
  me: { label: "我的", icon: "person-outline", activeIcon: "person" },
};

/**
 * 自定义底栏：React Navigation 默认标签在 Web/小屏会把 11px 中文裁成半行，
 * 这里自己排版（图标 22 + 标签 15 + 内边距），保证 375/390 宽都不裁字。
 */
export function BottomTabBar({
  state,
  descriptors,
  navigation,
  unread = 0,
}: BottomTabBarProps & { unread?: number }) {
  const insets = useSafeAreaInsets();
  const [keyboardOpen, setKeyboardOpen] = useState(false);

  useEffect(() => {
    const show = Keyboard.addListener("keyboardDidShow", () => setKeyboardOpen(true));
    const hide = Keyboard.addListener("keyboardDidHide", () => setKeyboardOpen(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  if (keyboardOpen) return null;

  return (
    <View
      style={[
        styles.bar,
        { paddingBottom: Math.max(insets.bottom, 8) },
      ]}
      accessibilityRole="tablist"
    >
      {state.routes.map((route, index) => {
        const meta = META[route.name];
        if (!meta) return null;
        const focused = state.index === index;
        const options = descriptors[route.key].options;
        const onPress = () => {
          const event = navigation.emit({
            type: "tabPress",
            target: route.key,
            canPreventDefault: true,
          });
          if (!focused && !event.defaultPrevented) {
            navigation.navigate(route.name, route.params);
          }
        };
        return (
          <Pressable
            key={route.key}
            onPress={onPress}
            accessibilityRole="tab"
            accessibilityLabel={typeof options.tabBarLabel === "string" ? options.tabBarLabel : meta.label}
            accessibilityState={{ selected: focused }}
            style={({ pressed }) => [styles.item, pressed && styles.pressed]}
          >
            <View style={styles.iconWrap}>
              <Icon
                name={focused ? meta.activeIcon : meta.icon}
                size={23}
                color={focused ? colors.green : colors.muted}
              />
              {route.name === "me" && unread > 0 ? (
                <View style={styles.badge}>
                  <Text variant="caption" color={colors.white} style={styles.badgeText}>
                    {unread > 9 ? "9+" : unread}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text
              variant="caption"
              color={focused ? colors.green : colors.muted}
              style={[styles.label, focused && styles.labelActive]}
            >
              {meta.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    paddingTop: 8,
    minHeight: layout.tabBarHeight,
  },
  item: {
    flex: 1,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "flex-start",
    gap: 1,
  },
  pressed: { opacity: 0.6 },
  iconWrap: { width: 28, height: 24, alignItems: "center", justifyContent: "center" },
  label: { fontSize: 12, lineHeight: 16 },
  labelActive: { fontWeight: "600" },
  badge: {
    position: "absolute",
    top: -2,
    right: -6,
    minWidth: 14,
    height: 14,
    borderRadius: 7,
    paddingHorizontal: 3,
    backgroundColor: colors.danger,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { fontSize: 10, lineHeight: 12, fontWeight: "600" },
});
