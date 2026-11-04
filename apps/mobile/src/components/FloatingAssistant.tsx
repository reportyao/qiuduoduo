import { useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, motion, shadows } from "@/theme/tokens";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Avatar } from "./ui/Avatar";

const SIZE = 56;

/**
 * 跨 Tab 常驻的 AI 实体：像 Muse 的头像一样悬浮在 4 个 Tab 之上。
 * 它不随页面滚动，滚动/切 Tab 都保持可见；点击进入助理对话。
 */
export function FloatingAssistant() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { meta } = usePersonaContent();
  const reduced = useReducedMotion();
  const float = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduced) return;
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

  return (
    <View pointerEvents="box-none" style={[styles.wrap, { top: insets.top + 4 }]}>
      <Pressable
        onPress={() => router.push("/assistant")}
        accessibilityRole="button"
        accessibilityLabel={`${meta.name}，打开助理`}
        hitSlop={8}
        style={styles.press}
      >
        <View style={styles.halo} />
        <Animated.View
          style={{
            transform: [
              { translateY: float.interpolate({ inputRange: [0, 1], outputRange: [0, -3] }) },
            ],
          }}
        >
          <Avatar source={meta.avatar} size={SIZE} online />
        </Animated.View>
      </Pressable>
    </View>
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
  press: { width: SIZE + 16, height: SIZE + 12, alignItems: "center", justifyContent: "center" },
  halo: {
    position: "absolute",
    width: SIZE + 18,
    height: SIZE + 18,
    borderRadius: (SIZE + 18) / 2,
    backgroundColor: colors.greenSoft,
    opacity: 0.55,
    ...shadows.float,
  },
});
