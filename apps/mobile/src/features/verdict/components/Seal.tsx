import { Pressable, StyleSheet, View } from "react-native";
import { colors, spacing } from "@/theme/tokens";
import { shortHash } from "@/lib/format";
import { Text } from "@/components/ui";

/** 4×4 指纹：由 hash 前 16 位映射透明度，肉眼可识别但不可逆。 */
export function HashGrid({
  hash,
  size = 5,
  gap = 3,
  color = colors.greenAccent,
}: {
  hash: string | null;
  size?: number;
  gap?: number;
  color?: string;
}) {
  const chars = (hash ?? "").slice(0, 16).padEnd(16, "0").split("");
  return (
    <View style={[styles.grid, { gap }]}>
      {chars.map((char, index) => {
        const nibble = Number.parseInt(char, 16);
        const opacity = Number.isNaN(nibble) ? 0.2 : 0.18 + (nibble / 15) * 0.82;
        return (
          <View
            key={`${char}-${index}`}
            style={{
              width: size,
              height: size,
              borderRadius: 1.5,
              backgroundColor: color,
              opacity,
            }}
          />
        );
      })}
    </View>
  );
}

export function SealLine({
  hash,
  sealed,
  onPress,
  dark = false,
}: {
  hash: string | null;
  sealed: boolean;
  onPress?: () => void;
  dark?: boolean;
}) {
  const content = (
    <View style={styles.line}>
      <HashGrid hash={hash} color={dark ? colors.greenAccent : colors.green} />
      <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted} style={styles.text}>
        {sealed ? `已封存 · ${shortHash(hash)}` : "尚未封存"}
      </Text>
      <View style={[styles.stamp, { borderColor: dark ? colors.greenAccent : colors.green }]}>
        <Text variant="caption" color={dark ? colors.greenAccent : colors.green}>封</Text>
      </View>
    </View>
  );
  if (!onPress) return content;
  return (
    <Pressable onPress={onPress} hitSlop={8} accessibilityRole="button" accessibilityLabel="查看封存与验证">
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", width: 29 },
  line: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingTop: spacing.base,
  },
  text: { flex: 1 },
  stamp: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});
