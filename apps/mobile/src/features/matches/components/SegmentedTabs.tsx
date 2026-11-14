import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

export type MatchTab = "live" | "results" | "predictions";

const TABS: { key: MatchTab; label: string }[] = [
  { key: "live", label: "即时" },
  { key: "results", label: "赛果" },
  { key: "predictions", label: "预测战绩" },
];

interface SegmentedTabsProps {
  value: MatchTab;
  onChange: (tab: MatchTab) => void;
  liveCount?: number;
}

/** 三段切换：始终同宽，切换不改变页面结构，避免列表跳动。 */
export function SegmentedTabs({ value, onChange, liveCount = 0 }: SegmentedTabsProps) {
  return (
    <View style={styles.wrap}>
      {TABS.map((tab) => {
        const active = value === tab.key;
        return (
          <Pressable
            key={tab.key}
            onPress={() => onChange(tab.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={tab.label}
            style={({ pressed }) => [
              styles.item,
              active && styles.active,
              pressed && !active && styles.pressed,
            ]}
          >
            <Text
              variant="smallStrong"
              color={active ? colors.white : colors.muted}
              numberOfLines={1}
            >
              {tab.label}
              {tab.key === "live" && liveCount > 0 ? ` ${liveCount}` : ""}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: colors.surfaceSunken,
    borderRadius: radii.pill,
    padding: 4,
    gap: 2,
    marginTop: spacing.md,
  },
  item: {
    flex: 1,
    minHeight: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  active: { backgroundColor: colors.brandPressed },
  pressed: { backgroundColor: colors.brandSoft },
});
