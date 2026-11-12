import { ScrollView, StyleSheet, View } from "react-native";
import type { Pulse } from "@/domain/focusAdapters";
import type { StreamResponse } from "@/domain/types";
import { currentTradeDateCn, formatDate, formatTime, shiftDateCn } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";
import { Chip, Sheet, Text } from "@/components/ui";

export function DateStrip({
  value,
  onChange,
}: {
  value: string;
  onChange: (date: string) => void;
}) {
  const base = currentTradeDateCn();
  const options = [
    { date: shiftDateCn(base, 0), label: "今天" },
    { date: shiftDateCn(base, -1), label: "昨天" },
    { date: shiftDateCn(base, -2), label: "前天" },
  ];
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.dateStrip}
    >
      {options.map((option) => (
        <Chip
          key={option.date}
          label={option.label}
          selected={value === option.date}
          onPress={() => onChange(option.date)}
        />
      ))}
      <View style={styles.dateLabel}>
        <Text variant="caption" color={colors.subtle}>{formatDate(value)}</Text>
      </View>
    </ScrollView>
  );
}

export function DataStatusSheet({
  visible,
  onClose,
  stream,
  pulse,
}: {
  visible: boolean;
  onClose: () => void;
  stream: StreamResponse | null;
  pulse?: Pulse | null;
}) {
  const marketPending = stream?.watch.some((v) => v.gates.market === "pending_data") ?? false;
  const modelPending = stream?.watch.some((v) => v.gates.model === "pending_data") ?? false;
  const rows = pulse?.sources?.length
    ? pulse.sources.map((source) => ({
        name: ({
          sportmonks: "预测/市场",
          intel: "情报",
          sporttery: "竞彩",
          intl: "市场",
          xg: "模型",
          lineups: "阵容",
          standings: "积分榜",
          sportmonks_intel: "阵容/积分榜",
          schedule: "赛程",
          results: "赛果",
        } as Record<string, string>)[source.key] || source.label.replace(/Sportmonks\s*·?\s*/gi, ""),
        status: "已同步",
        ok: source.status !== "missing",
      }))
    : [
        { name: "竞彩官方 SP", status: "已接入", ok: true },
        { name: "预测/市场", status: marketPending ? "部分同步" : "已接入", ok: !marketPending },
        { name: "阵容/积分榜", status: "已接入", ok: true },
        { name: "AI 情报", status: "已接入", ok: true },
        { name: "国际盘（兜底）", status: marketPending ? "部分同步" : "已接入", ok: !marketPending },
        { name: "xG 强度模型", status: modelPending ? "部分同步" : "已接入", ok: !modelPending },
        { name: "赛程 / 停售", status: "已同步", ok: true },
      ];
  return (
    <Sheet visible={visible} onClose={onClose} title="数据状态" subtitle="每条预测都带来源与截止时间。">
      <Text variant="small" color={colors.muted} style={styles.paragraph}>
        {stream?.stats.gateNote || "模型：抽水阈值 · 多源分歧 · 收缩置信。"}
      </Text>
      <View style={styles.sourceList}>
        {rows.map((row) => (
          <View key={row.name} style={styles.sourceRow}>
            <Text variant="small">{row.name}</Text>
            <View style={styles.sourceStatus}>
              <View style={[styles.gateDot, { backgroundColor: row.ok ? colors.green : colors.amber }]} />
              <Text variant="caption" color={row.ok ? colors.green : colors.amber}>{row.status}</Text>
            </View>
          </View>
        ))}
      </View>
      <Text variant="caption" color={colors.subtle} style={styles.paragraph}>
        所有展示数据都带更新时间；完整分片在比赛详情。
        {pulse ? ` 今日 ${pulse.counts.matches} 场、${pulse.dataPoints} 个数据点，更新于 ${formatTime(pulse.asOf)}。` : ""}
        {!pulse && stream?.generatedAt ? ` 最近更新：${formatTime(stream.generatedAt)}。` : ""}
      </Text>
    </Sheet>
  );
}

/** 底部合规/技术脚注。所有页面复用，避免各处写不同版本。 */
export function LegalFooter({ text }: { text: string }) {
  return (
    <Text variant="caption" color={colors.subtle} center style={styles.footer}>
      {text}
    </Text>
  );
}

const styles = StyleSheet.create({
  dateStrip: { gap: spacing.xs, alignItems: "center", paddingVertical: spacing.sm },
  dateLabel: { marginLeft: spacing.xs },
  paragraph: { lineHeight: 20 },
  sourceList: { marginTop: spacing.base, gap: spacing.xs },
  sourceRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  sourceStatus: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  gateDot: { width: 7, height: 7, borderRadius: 4 },
  footer: { marginTop: spacing.x4, paddingHorizontal: spacing.x4, lineHeight: 18 },
});
