import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { EvidenceItem } from "@/domain/types";
import { formatDateTime } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Card, Chip, Icon, Text } from "@/components/ui";

const clean = (text: string) => text.replace(/Sportmonks\s*·?\s*/gi, "").trim();

function tagLabel(tag?: string): string {
  return /背景|未定价|未验证/.test(tag ?? "") ? "数据" : "核心";
}

export function EvidenceList({
  items,
  cutoff,
}: {
  items: EvidenceItem[];
  cutoff: string;
}) {
  const [expanded, setExpanded] = useState<number | null>(0);
  const rows = items.filter((item) =>
    !/非五大联赛|窗口数据不足|W4 接入/.test(String(item.detail ?? "")));

  return (
    <Card padded={false} style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="h3">预测依据</Text>
          <Text variant="caption" color={colors.muted}>
            {rows.length} 条 · 截止 {cutoff ? formatDateTime(cutoff) : "同步中"}
          </Text>
        </View>
        <Text variant="caption" color={colors.subtle}>逐条可溯源</Text>
      </View>

      {rows.length === 0 ? (
        <View style={styles.empty}>
          <Text variant="small" color={colors.muted}>这场暂无公开依据。</Text>
        </View>
      ) : (
        rows.map((item, index) => {
          const open = expanded === index;
          const label = tagLabel(item.tag);
          const tone = label === "核心" ? "green" : "neutral";
          return (
            <Pressable
              key={`${item.title}-${index}`}
              onPress={() => setExpanded(open ? null : index)}
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              accessibilityLabel={`${clean(item.title)}，${label}`}
              style={({ pressed }) => [
                styles.row,
                index < rows.length - 1 && styles.rowLine,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.rowHead}>
                <Chip label={label} tone={tone} />
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
