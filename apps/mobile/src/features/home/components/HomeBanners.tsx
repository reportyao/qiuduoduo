import { Pressable, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import type { OnSaleItem, StreamResponse } from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";
import { countdownText, formatTime, parseCnDateTime } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, gradients, radii, spacing } from "@/theme/tokens";
import { Icon, StatusDot, Text } from "@/components/ui";

export function DataStatusBanner({
  stream,
  onPress,
}: {
  stream: StreamResponse | null;
  onPress: () => void;
}) {
  const { copy } = usePersonaContent();
  const total = stream?.stats.total ?? 0;
  const promoted = stream?.stats.promoted ?? 0;
  const screening = stream?.stats.screening ?? 0;
  const text =
    stream?.mode === "rest_day"
      ? "非比赛日 · 今天没有竞彩足球场次"
      : total > 0
        ? copy.envLive(total, promoted, screening)
        : copy.envEmpty;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="查看数据状态与来源"
      style={({ pressed }) => [styles.dataBanner, pressed && styles.pressed]}
    >
      <StatusDot color={stream?.mode === "rest_day" ? colors.amber : colors.green} size={7} />
      <Text variant="small" color={colors.ink} style={styles.flex} numberOfLines={2}>
        {text}
      </Text>
      <Icon name="chevron-forward" size={15} color={colors.subtle} />
    </Pressable>
  );
}

export function SaleBanner({
  onsale,
  onPress,
}: {
  onsale: OnSaleItem[];
  onPress: () => void;
}) {
  const { copy } = usePersonaContent();
  const now = useNow(30_000);
  const upcoming = onsale
    .map((item) => ({ item, at: parseCnDateTime(item.saleClose)?.getTime() ?? 0 }))
    .filter((entry) => entry.at > now)
    .sort((a, b) => a.at - b.at)[0];
  const next = upcoming?.item;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="查看今日在售"
      style={({ pressed }) => [styles.saleBanner, pressed && styles.pressed]}
    >
      <Text variant="smallStrong" color={colors.amber} numberOfLines={1} style={styles.flex}>
        {next ? `${copy.saleTitle} ${formatTime(next.saleClose)} · ${countdownText(next.saleClose, now)}` : "今日在售待同步"}
      </Text>
      <View style={styles.saleRight}>
        <Text variant="smallStrong" color={colors.amber}>今日在售 {onsale.length} 场</Text>
        <Icon name="chevron-forward" size={14} color={colors.amber} />
      </View>
    </Pressable>
  );
}

export function ParlayBanner({ onPress }: { onPress: () => void }) {
  const { copy } = usePersonaContent();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="打开串关体检"
      style={({ pressed }) => [{ opacity: pressed ? 0.92 : 1 }]}
    >
      <LinearGradient
        colors={gradients.parlay}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.parlay}
      >
        <View style={styles.flex}>
          <Text variant="h3" color={colors.white}>{copy.parlayTitle}</Text>
          <Text variant="caption" color="rgba(255,255,255,0.78)" style={styles.parlaySub}>
            {copy.parlaySub}
          </Text>
        </View>
        <View style={styles.parlayCta}>
          <Text variant="smallStrong" color={colors.white}>{copy.parlayCta}</Text>
          <Icon name="arrow-forward" size={15} color={colors.white} />
        </View>
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  pressed: { opacity: 0.78 },
  dataBanner: {
    marginTop: spacing.base,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    minHeight: 46,
  },
  saleBanner: {
    marginTop: spacing.sm,
    backgroundColor: colors.amberSoft,
    borderWidth: 1,
    borderColor: colors.amberLine,
    borderRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    minHeight: 46,
  },
  saleRight: { flexDirection: "row", alignItems: "center", gap: 2 },
  parlay: {
    marginTop: spacing.sm,
    borderRadius: radii.xl,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xl,
    minHeight: 84,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
  },
  parlaySub: { marginTop: 3, lineHeight: 17 },
  parlayCta: { flexDirection: "row", alignItems: "center", gap: 4 },
});
