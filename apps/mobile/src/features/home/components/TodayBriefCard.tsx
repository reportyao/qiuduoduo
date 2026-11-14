import { useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Card, Chip, Text } from "@/components/ui";
import { countdownText, currentTradeDateCn, formatDate, formatTime, parseCnDateTime } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, radii, spacing } from "@/theme/tokens";
import type { BriefMatchOption } from "./BriefMatchPicker";

interface TodayBriefCardProps {
  date: string;
  total: number;
  predicted: number;
  published: number;
  onsale: number;
  options: BriefMatchOption[];
  onSelect: (option: BriefMatchOption) => void;
  onOpenData: () => void;
}

/**
 * 今日简报：把“今天看哪场”压缩成一张卡。
 * 只回答三件事：有多少场、下一场什么时候、前三个最值得看的场次。
 */
export function TodayBriefCard({
  date,
  total,
  predicted,
  published,
  onsale,
  options,
  onSelect,
  onOpenData,
}: TodayBriefCardProps) {
  const now = useNow(60_000);
  const upcoming = useMemo(
    () => options
      .map((option) => ({ option, time: parseCnDateTime(option.kickoff)?.getTime() ?? 0 }))
      .filter((row) => row.time > now)
      .sort((a, b) => a.time - b.time),
    [options, now],
  );
  const next = upcoming[0]?.option ?? null;
  const highlights = useMemo(
    () => options
      .filter((option) => option.tier === "verified" || option.tier === "market_reference")
      .slice(0, 3),
    [options],
  );

  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="overline" color={colors.brand}>
            {date === currentTradeDateCn() ? "今日简报" : "历史简报"}
          </Text>
          <Text variant="h2">{formatDate(date)}</Text>
        </View>
        <Pressable onPress={onOpenData} accessibilityRole="button" accessibilityLabel="查看数据状态">
          <Chip label="数据状态" tone="neutral" />
        </Pressable>
      </View>

      <View style={styles.stats}>
        <Stat label="场次" value={total} />
        <Stat label="有预测" value={predicted} tone={colors.brand} />
        <Stat label="已发布" value={published} tone={colors.brand} />
        <Stat label="在售" value={onsale} />
      </View>

      {next ? (
        <View style={styles.next}>
          <View style={styles.flex}>
            <Text variant="caption" color={colors.muted}>下一场</Text>
            <Text variant="h3" numberOfLines={1}>
              {next.home} vs {next.away}
            </Text>
            <Text variant="caption" color={colors.muted}>
              {formatTime(next.kickoff)} · {countdownText(next.kickoff, now)}
            </Text>
          </View>
          <Pressable
            onPress={() => onSelect(next)}
            accessibilityRole="button"
            accessibilityLabel={`查看 ${next.home} 对 ${next.away}`}
            style={styles.nextButton}
          >
            <Text variant="smallStrong" color={colors.brand}>看这场</Text>
          </Pressable>
        </View>
      ) : (
        <Text variant="small" color={colors.muted}>今日场次已完赛或暂无待开赛比赛。</Text>
      )}

      {highlights.length ? (
        <View style={styles.list}>
          <Text variant="captionStrong" color={colors.muted}>重点场次</Text>
          {highlights.map((option) => (
            <Pressable
              key={option.matchId}
              onPress={() => onSelect(option)}
              accessibilityRole="button"
              accessibilityLabel={`查看 ${option.home} 对 ${option.away}`}
              style={({ pressed }) => [styles.row, pressed && styles.pressed]}
            >
              <View style={styles.flex}>
                <Text variant="smallStrong" numberOfLines={1}>
                  {option.home} vs {option.away}
                </Text>
                <Text variant="caption" color={colors.subtle} numberOfLines={1}>
                  {formatTime(option.kickoff)} · {option.league || "未分类"}
                </Text>
              </View>
              <Text variant="captionStrong" color={colors.brand}>详情 ›</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </Card>
  );
}

function Stat({
  label,
  value,
  tone = colors.ink,
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <View style={styles.stat}>
      <Text variant="h3" color={tone}>{value}</Text>
      <Text variant="caption" color={colors.muted}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: spacing.md },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  flex: { flex: 1 },
  stats: { flexDirection: "row", gap: spacing.xl },
  stat: { gap: 1 },
  next: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.brandSoft,
  },
  nextButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
  },
  list: { gap: spacing.xs },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  pressed: { opacity: 0.72 },
});
