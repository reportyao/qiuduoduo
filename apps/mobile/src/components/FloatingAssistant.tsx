import { useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { motion } from "@/theme/tokens";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useFloatingStore } from "@/features/assistant/floatingStore";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Avatar } from "./ui/Avatar";

const SIZE = 56;

/**
 * 跨 Tab 常驻的 AI 实体：像 Muse 的头像一样悬浮在 4 个 Tab 之上。
 * 它不随页面滚动，滚动/切 Tab 都保持可见；点击进入助理对话。
 */
export function FloatingAssistant() {
  const insets = useSafeAreaInsets();
  const openPicker = useFloatingStore((s) => s.openPicker);
  const { meta } = usePersonaContent();
  const reduced = useReducedMotion();
  const compact = useFloatingStore((s) => s.compact);
  const float = useRef(new Animated.Value(0)).current;
  const squeeze = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduced) {
      float.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(float, {
          toValue: 1,
          duration: motion.mascot / 2,
          useNativeDriver: true,
        }),
        Animated.timing(float, {
          toValue: 0,
          duration: motion.mascot / 2,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [float, reduced]);

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

  return (
    <Animated.View
      pointerEvents="box-none"
      style={[
        styles.wrap,
        { top: insets.top + 4 },
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
        <Animated.View
          style={{
            transform: [
              { translateY: float.interpolate({ inputRange: [0, 1], outputRange: [0, -3] }) },
            ],
          }}
        >
          <Avatar source={meta.avatar} size={SIZE} online ring={false} bare />
        </Animated.View>
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
