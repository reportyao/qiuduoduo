import { memo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "@/components/ui";
import { formatTime } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";

export interface BriefMatchOption {
  matchId: string;
  verdictId: string | null;
  home: string;
  away: string;
  kickoff: string;
  status?: string | null;
}

function statusLabel(option: BriefMatchOption): string {
  // promoted 只代表三关全过，不等于已经发布；避免在开场条上误标“已发布”。
  if (option.status === "promoted") return "三关通过";
  if (option.status === "screening") return "复核中";
  if (option.status === "killed") return "未发布";
  return option.verdictId ? "已复核" : "待解读";
}

/**
 * 首页开场的选择条：助理先问“先看哪场”，用户点一场才展开该场预测。
 * 默认只露前 5 场，其余通过“全部 N 场”进入完整列表。
 */
export const BriefMatchPicker = memo(function BriefMatchPicker({
  options,
  total,
  expanded,
  onSelect,
  onExpandAll,
}: {
  options: BriefMatchOption[];
  total: number;
  expanded: boolean;
  onSelect: (option: BriefMatchOption) => void;
  onExpandAll: () => void;
}) {
  if (options.length === 0) return null;
  const visible = expanded ? options : options.slice(0, 5);
  const hiddenCount = Math.max(0, total - visible.length);

  return (
    <View style={styles.wrap}>
      <Text variant="caption" color={colors.muted} style={styles.lead}>
        先看哪场？点一场，我把这场展开说。
      </Text>

      <View style={styles.list}>
        {visible.map((option) => (
          <Pressable
            key={option.matchId}
            onPress={() => onSelect(option)}
            accessibilityRole="button"
            accessibilityLabel={`${option.home} 对 ${option.away}，${formatTime(option.kickoff)} 开赛`}
            style={({ pressed }) => [styles.item, pressed && styles.pressed]}
          >
            <View style={styles.itemMain}>
              <Text variant="captionStrong" numberOfLines={1} style={styles.matchText}>
                {option.home} vs {option.away}
              </Text>
              <Text variant="caption" color={colors.subtle}>
                {formatTime(option.kickoff)} · {statusLabel(option)}
              </Text>
            </View>
            <Text variant="caption" color={colors.green}>展开 ›</Text>
          </Pressable>
        ))}
      </View>

      {hiddenCount > 0 ? (
        <Pressable
          onPress={onExpandAll}
          accessibilityRole="button"
          accessibilityLabel={`展开全部 ${total} 场比赛`}
          hitSlop={6}
          style={styles.more}
        >
          <Text variant="captionStrong" color={colors.green}>
            全部 {total} 场 · 展开 ›
          </Text>
        </Pressable>
      ) : null}

      <Text variant="caption" color={colors.subtle} style={styles.hint}>
        也可以点顶部头像，随时打开今日比赛列表。
      </Text>
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, marginTop: spacing.sm },
  lead: { lineHeight: 18 },
  list: { gap: spacing.xs },
  item: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.base,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  pressed: { opacity: 0.72 },
  itemMain: { flex: 1, gap: 2 },
  matchText: { lineHeight: 18 },
  more: { alignSelf: "flex-start", paddingVertical: 2 },
  hint: { lineHeight: 17 },
});
