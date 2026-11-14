import { useEffect, useRef } from "react";
import { Animated, Image, StyleSheet, View } from "react-native";
import { colors, spacing } from "@/theme/tokens";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Text } from "./ui/Text";

/** 启动/水合期间的稳定占位，避免闪白屏和「先空后有」的抖动。 */
export function BootScreen() {
  const pulse = useRef(new Animated.Value(0.4)).current;
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.4, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, reduced]);

  return (
    <View style={styles.wrap}>
      <Animated.View style={{ opacity: pulse }}>
        <Image
          source={require("../../assets/mascot/zhuanjia.png")}
          style={styles.avatar}
          resizeMode="cover"
        />
      </Animated.View>
      <Text variant="h3" style={styles.title}>球多多</Text>
      <Text variant="small" color={colors.muted}>正在校准今日数据…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
  },
  avatar: {
    width: 96,
    height: 96,
    borderRadius: 48,
    marginBottom: spacing.base,
    backgroundColor: colors.white,
  },
  title: { fontSize: 22, letterSpacing: 1 },
});
