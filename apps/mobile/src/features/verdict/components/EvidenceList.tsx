import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { EvidenceItem } from "@/domain/types";
import { formatDateTime } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Card, Chip, Icon, Text } from "@/components/ui";

const clean = (text: string) => text.replace(/Sportmonks\s*·?\s*/gi, "").trim();

export function EvidenceList({
  items,
  cutoff,
}: {
  items: EvidenceItem[];
  cutoff: string;
}) {
  const [expanded, setExpanded] = useState<number | null>(0);

  return (
    <Card padded={false} style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="h3">预测依据</Text>
          <Text variant="caption" color={colors.muted}>
            {items.length} 条 · 截止 {cutoff ? formatDateTime(cutoff) : "同步中"}
          </Text>
        </View>
        <Text variant="caption" color={colors.subtle}>逐条可溯源</Text>
      </View>

      {items.length === 0 ? (
        <View style={styles.empty}>
          <Text variant="small" color={colors.muted}>这场还没有可展示的依据。数据没到，不编。</Text>
        </View>
      ) : (
        items.map((item, index) => {
          const open = expanded === index;
          const tone =
            item.tag.includes("未定价") || item.tag.includes("背景")
              ? "neutral"
              : "green";
          return (
            <Pressable
              key={`${item.title}-${index}`}
              onPress={() => setExpanded(open ? null : index)}
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              accessibilityLabel={`${clean(item.title)}，${item.tag}`}
              style={({ pressed }) => [
                styles.row,
                index < items.length - 1 && styles.rowLine,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.rowHead}>
                <Chip label={item.tag} tone={tone} />
                <Icon name={open ? "chevron-up" : "chevron-down"} size={15} color={colors.subtle} />
              </View>
              <Text variant="bodyStrong">{clean(item.title)}</Text>
              <Text variant="small" color={colors.muted} numberOfLines={open ? undefined : 2} style={styles.detail}>
                {clean(item.detail)}
              </Text>
            </Pressable>
          );
        })
      )}
      <Text variant="caption" color={colors.subtle} style={styles.note}>
        「已核验 / 已计入」才进入预测；「仅背景」不参与模型，只作人话解释。
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base },
  head: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.base,
    padding: spacing.xl,
    paddingBottom: spacing.base,
  },
  flex: { flex: 1, gap: 2 },
  row: { paddingHorizontal: spacing.xl, paddingVertical: spacing.base, gap: spacing.xs },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { backgroundColor: colors.bgElevated },
  rowHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  detail: { lineHeight: 19 },
  source: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.bgElevated,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
    marginTop: 2,
  },
  sourceText: { flex: 1 },
  note: { padding: spacing.xl, paddingTop: spacing.sm, lineHeight: 17 },
  empty: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xl },
});
