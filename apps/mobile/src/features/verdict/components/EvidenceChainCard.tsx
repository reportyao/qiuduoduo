import { useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { EvidenceItem } from "@/domain/types";
import { formatDateTime } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Card, Chip, Icon, type IconName, Text } from "@/components/ui";

const clean = (text: string) => text.replace(/Sportmonks\s*·?\s*/gi, "").trim();

function tagLabel(tag?: string): string {
  return /背景|未定价|未验证/.test(tag ?? "") ? "数据" : "核心";
}

/** 按来源关键词映射图标；未知来源回退到链接图标。 */
function sourceIcon(item: EvidenceItem): IconName {
  const hay = `${item.source} ${item.title}`.toLowerCase();
  if (/sporttery|竞彩/.test(hay)) return "stats-chart-outline";
  if (/pinnacle|国际盘|the-odds/.test(hay)) return "globe-outline";
  if (/模型|dixon|dc\b/.test(hay)) return "analytics-outline";
  if (/sportmonks|25\s*维|正确比分/.test(hay)) return "football-outline";
  return "link-outline";
}

function sourceLabel(item: EvidenceItem): string {
  const raw = clean(String(item.source ?? ""));
  if (!raw) return "";
  // src 通常是「来源 · cutoff 2026-11-13T03:09:25+08:00」；拆成来源名 + 时间。
  const match = raw.match(/^(.*?)\s*·\s*cutoff\s*(.+)$/i);
  if (!match) return raw;
  return match[1];
}

function sourceCutoff(item: EvidenceItem): string {
  const match = String(item.source ?? "").match(/cutoff\s*(.+)$/i);
  if (!match) return "";
  const date = new Date(match[1].replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")} 截止`;
}

/**
 * 证据链：把「这个判断依据什么」摊开。
 * 每条证据一行——来源图标、标题、内容；核心项墨绿 chip，数据项灰色 chip。
 */
export function EvidenceChainCard({
  items,
  cutoff,
}: {
  items: EvidenceItem[];
  cutoff: string;
}) {
  const [expanded, setExpanded] = useState<number | null>(0);
  const rows = useMemo(
    () => items.filter((item) =>
      !/非五大联赛|窗口数据不足|W4 接入/.test(String(item.detail ?? ""))),
    [items],
  );
  const sources = useMemo(
    () => new Set(rows.map((item) => sourceLabel(item) || item.source || "未知")),
    [rows],
  );

  return (
    <Card padded={false} style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="overline" color={colors.green}>证据链</Text>
          <Text variant="h3">每条判断都有来源</Text>
          <Text variant="caption" color={colors.muted}>
            {rows.length} 条 · {sources.size} 个来源 · 截止 {cutoff ? formatDateTime(cutoff) : "同步中"}
          </Text>
        </View>
      </View>

      {rows.length === 0 ? (
        <View style={styles.empty}>
          <Text variant="small" color={colors.muted}>这场暂无公开依据；没有依据就不给方向。</Text>
        </View>
      ) : (
        rows.map((item, index) => {
          const open = expanded === index;
          const label = tagLabel(item.tag);
          const source = sourceLabel(item);
          const cutoffText = sourceCutoff(item);
          return (
            <Pressable
              key={`${item.title}-${index}`}
              onPress={() => setExpanded(open ? null : index)}
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              accessibilityLabel={`${clean(item.title)}，${label}，来源 ${source || "未知"}`}
              style={({ pressed }) => [
                styles.row,
                index < rows.length - 1 && styles.rowLine,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.iconWrap}>
                <Icon name={sourceIcon(item)} size={18} color={colors.green} />
              </View>
              <View style={styles.body}>
                <View style={styles.titleRow}>
                  <Text variant="bodyStrong" style={styles.flex} numberOfLines={open ? undefined : 1}>
                    {clean(item.title)}
                  </Text>
                  <Chip label={label} tone={label === "核心" ? "green" : "neutral"} />
                </View>
                <Text
                  variant="small"
                  color={colors.muted}
                  numberOfLines={open ? undefined : 2}
                  style={styles.detail}
                >
                  {clean(item.detail)}
                </Text>
                <View style={styles.sourceRow}>
                  <Icon name="time-outline" size={13} color={colors.subtle} />
                  <Text variant="caption" color={colors.subtle} style={styles.flex} numberOfLines={1}>
                    {source || "来源待同步"}
                    {cutoffText ? ` · ${cutoffText}` : ""}
                  </Text>
                  <Icon name={open ? "chevron-up" : "chevron-down"} size={14} color={colors.subtle} />
                </View>
              </View>
            </Pressable>
          );
        })
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base },
  head: { padding: spacing.x4, paddingBottom: spacing.md, gap: spacing.xs },
  flex: { flex: 1, gap: 1 },
  row: {
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.x4,
    paddingVertical: spacing.md,
  },
  rowLine: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line },
  pressed: { backgroundColor: colors.bgElevated },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: radii.md,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  body: { flex: 1, gap: 3 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  detail: { lineHeight: 19 },
  sourceRow: { flexDirection: "row", alignItems: "center", gap: 3, marginTop: 2 },
  empty: { paddingHorizontal: spacing.x4, paddingBottom: spacing.x4 },
});
