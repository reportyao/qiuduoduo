import { useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { SportmonksPredictionHighlight } from "@/domain/types";
import { ProbabilityBreakdown, Text } from "@/components/ui";
import { colors, spacing } from "@/theme/tokens";
import { predictionDistribution } from "../predictionData";

type GroupKey = "main" | "goals" | "halves" | "corners" | "score" | "other";

const GROUPS: { key: GroupKey; title: string; note: string }[] = [
  { key: "main", title: "主流玩法", note: "胜平负 / 双重机会 / 先进球" },
  { key: "goals", title: "大小球", note: "全场 / 主队 / 客队进球线" },
  { key: "halves", title: "半场与半全场", note: "半场胜平负 / 半全场" },
  { key: "corners", title: "角球", note: "角球大小与走水" },
  { key: "score", title: "正确比分", note: "全部比分桶" },
  { key: "other", title: "其他维度", note: "双方进球等" },
];

function groupOf(key: string): GroupKey {
  if (key === "FULLTIME_RESULT_PROBABILITY"
      || key === "DOUBLE_CHANCE_PROBABILITY"
      || key === "TEAM_TO_SCORE_FIRST_PROBABILITY") return "main";
  if (key.startsWith("OVER_UNDER_")
      || key.startsWith("HOME_OVER_UNDER_")
      || key.startsWith("AWAY_OVER_UNDER_")) return "goals";
  if (key === "FIRST_HALF_WINNER_PROBABILITY"
      || key === "HTFT_PROBABILITY") return "halves";
  if (key.startsWith("CORNERS_OVER_UNDER_")) return "corners";
  if (key === "CORRECT_SCORE_PROBABILITY") return "score";
  return "other";
}

/**
 * 25 维预测分组板：默认每组只露前三项，避免一屏被 25 行概率淹没。
 * 正确比分整组保留完整分布，用概率格而不是文字串。
 */
export function PredictionGroupBoard({
  highlights,
}: {
  highlights: SportmonksPredictionHighlight[];
}) {
  const [open, setOpen] = useState<Record<GroupKey, boolean>>({
    main: true, goals: true, halves: false, corners: false, score: false, other: false,
  });
  const grouped = useMemo(() => {
    const map = new Map<GroupKey, SportmonksPredictionHighlight[]>();
    for (const item of highlights) {
      const key = groupOf(item.key);
      map.set(key, [...(map.get(key) ?? []), item]);
    }
    return map;
  }, [highlights]);

  return (
    <View style={styles.wrap}>
      {GROUPS.map((group) => {
        const items = grouped.get(group.key) ?? [];
        if (!items.length) return null;
        const expanded = open[group.key];
        const visible = expanded ? items : items.slice(0, 3);
        return (
          <View key={group.key} style={styles.group}>
            <Pressable
              onPress={() => setOpen((prev) => ({ ...prev, [group.key]: !prev[group.key] }))}
              accessibilityRole="button"
              accessibilityLabel={`${expanded ? "收起" : "展开"}${group.title}`}
              style={styles.head}
            >
              <View style={styles.flex}>
                <Text variant="smallStrong">{group.title}</Text>
                <Text variant="caption" color={colors.subtle}>{group.note}</Text>
              </View>
              <Text variant="captionStrong" color={colors.green}>
                {items.length} 项 · {expanded ? "收起" : "展开"}
              </Text>
            </Pressable>
            <View>
              {visible.map((item, index) => {
                const dist = predictionDistribution(item);
                return (
                  <View
                    key={item.key}
                    style={[styles.item, index < visible.length - 1 && styles.itemLine]}
                  >
                    <View style={styles.itemHead}>
                      <Text variant="captionStrong" style={styles.flex} numberOfLines={1}>
                        {item.label}
                      </Text>
                      <Text variant="caption" color={colors.green} numberOfLines={1}>
                        {dist.predictedLabel} {dist.predictedValue.toFixed(1)}%
                      </Text>
                    </View>
                    <ProbabilityBreakdown
                      items={dist.items}
                      predictedKey={dist.predictedKey}
                    />
                  </View>
                );
              })}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.md },
  group: { gap: spacing.xs },
  head: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1 },
  item: { paddingVertical: spacing.md, gap: 2 },
  itemLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  itemHead: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm },
});
