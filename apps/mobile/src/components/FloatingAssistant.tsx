import { useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useFloatingStore } from "@/features/assistant/floatingStore";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Avatar } from "./ui/Avatar";

const SIZE = 56;

/**
 * 跨 Tab 的 AI 实体：停在首屏顶部，点击进入助理对话。
 * 页面滚动阅读或底部弹层打开时收起，避免压住正文和弹层。
 */
export function FloatingAssistant() {
  const insets = useSafeAreaInsets();
  const openPicker = useFloatingStore((s) => s.openPicker);
  const { meta } = usePersonaContent();
  const reduced = useReducedMotion();
  const compact = useFloatingStore((s) => s.compact);
  const sheetOpen = useFloatingStore((s) => s.sheetDepth > 0);
  const hidden = compact || sheetOpen;
  const squeeze = useRef(new Animated.Value(0)).current;
  const reveal = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (reduced) {
      squeeze.setValue(compact ? 1 : 0);
      return;
    }
    const animation = Animated.timing(squeeze, {
      toValue: compact ? 1 : 0,
      duration: 220,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [compact, reduced, squeeze]);

  useEffect(() => {
    if (reduced) {
      reveal.setValue(hidden ? 0 : 1);
      return;
    }
    const animation = Animated.timing(reveal, {
      toValue: hidden ? 0 : 1,
      duration: hidden ? 140 : 200,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [hidden, reduced, reveal]);

  return (
    <Animated.View
      pointerEvents={hidden ? "none" : "box-none"}
      accessibilityElementsHidden={hidden}
      importantForAccessibility={hidden ? "no-hide-descendants" : "auto"}
      style={[
        styles.wrap,
        { top: insets.top + 4, opacity: reveal },
        {
          transform: [
            { translateY: squeeze.interpolate({ inputRange: [0, 1], outputRange: [0, -2] }) },
            { scale: squeeze.interpolate({ inputRange: [0, 1], outputRange: [1, 0.72] }) },
          ],
        },
      ]}
    >
      <Pressable
        onPress={openPicker}
        accessibilityRole="button"
        accessibilityLabel={`${meta.name}，看今日比赛`}
        hitSlop={10}
        style={styles.press}
      >
        <View>
          <Avatar source={meta.avatar} size={SIZE} online ring={false} bare />
        </View>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: 0,
    right: 0,
    alignItems: "center",
    zIndex: 30,
  },
  press: {
    width: SIZE + 16,
    height: SIZE + 12,
    alignItems: "center",
    justifyContent: "center",
  },
});
