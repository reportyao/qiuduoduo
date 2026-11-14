import { Pressable, StyleSheet, View } from "react-native";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

export type DetailSection = "overview" | "predictions" | "markets" | "review";

const SECTIONS: { key: DetailSection; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "predictions", label: "预测" },
  { key: "markets", label: "市场" },
  { key: "review", label: "复盘" },
];

/**
 * 详情页分段：把一条长滚动拆成四个工作台。
 * 概览给结论，预测给 25 维，市场给对照，复盘给赛后归因。
 */
export function DetailSectionTabs({
  value,
  onChange,
}: {
  value: DetailSection;
  onChange: (section: DetailSection) => void;
}) {
  return (
    <View style={styles.wrap} accessibilityRole="tablist">
      {SECTIONS.map((section) => {
        const active = value === section.key;
        return (
          <Pressable
            key={section.key}
            onPress={() => onChange(section.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={section.label}
            style={({ pressed }) => [
              styles.item,
              active && styles.active,
              pressed && !active && styles.pressed,
            ]}
          >
            <Text variant="smallStrong" color={active ? colors.white : colors.muted}>
              {section.label}
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
    gap: 2,
    padding: 4,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceSunken,
    marginVertical: spacing.md,
  },
  item: {
    flex: 1,
    minHeight: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  active: { backgroundColor: colors.brand },
  pressed: { backgroundColor: colors.brandSoft },
});
