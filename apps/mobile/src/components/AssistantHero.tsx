import { useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet, View } from "react-native";
import { colors, motion, spacing, type } from "@/theme/tokens";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { Avatar } from "./ui/Avatar";
import { Text } from "./ui/Text";

interface AssistantHeroProps {
  onPress: () => void;
  hint?: string;
}

/**
 * 首页顶部的 AI 实体。它属于滚动内容，不是固定头部 —— 滚动时自然滚出，
 * 满足「Muse 式」而不是滚动就压缩。呼吸/浮动只做 2% 级别，低性能设备也稳。
 */
export function AssistantHero({ onPress, hint }: AssistantHeroProps) {
  const { meta: persona, copy } = usePersonaContent();
  const reduced = useReducedMotion();
  const float = useRef(new Animated.Value(0)).current;
  const halo = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduced) return;
    const floatLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(float, { toValue: 1, duration: motion.mascot / 2, useNativeDriver: true }),
        Animated.timing(float, { toValue: 0, duration: motion.mascot / 2, useNativeDriver: true }),
      ]),
    );
    const haloLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(halo, { toValue: 1, duration: motion.mascot / 2, useNativeDriver: true }),
        Animated.timing(halo, { toValue: 0, duration: motion.mascot / 2, useNativeDriver: true }),
      ]),
    );
    floatLoop.start();
    haloLoop.start();
    return () => {
      floatLoop.stop();
      haloLoop.stop();
    };
  }, [float, halo, reduced]);

  return (
    <View style={styles.wrap}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={`${persona.name}，点我看今日全部比赛`}
        style={styles.press}
      >
        <Animated.View
          style={[
            styles.halo,
            {
              opacity: halo.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0.7] }),
              transform: [
                { scale: halo.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1.06] }) },
              ],
            },
          ]}
        />
        <Animated.View
          style={{
            transform: [
              { translateY: float.interpolate({ inputRange: [0, 1], outputRange: [0, -4] }) },
            ],
          }}
        >
          <Avatar source={persona.avatar} size={92} online />
        </Animated.View>
        <Text variant="bodyStrong" style={styles.name}>{persona.name}</Text>
        <Text variant="caption" color={colors.muted} numberOfLines={1} style={styles.hint}>
          {hint ?? copy.hintMatches}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", paddingTop: spacing.sm, paddingBottom: spacing.xs },
  press: { alignItems: "center", minWidth: 200 },
  halo: {
    position: "absolute",
    top: -8,
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.greenSoft,
  },
  name: { marginTop: spacing.xs, fontSize: type.bodyStrong.fontSize },
  hint: { marginTop: 1 },
});
