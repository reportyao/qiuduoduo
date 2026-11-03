import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import type { AvoidItem, PostmortemSummary, RestDay, StreamResponse } from "@/domain/types";
import { currentTradeDateCn, formatDate, formatTime, shiftDateCn } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Button, Card, Chip, Icon, Sheet, Text } from "@/components/ui";
import { gateTone } from "@/features/verdict/components/Gates";

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

export function FeedSummary({ stream }: { stream: StreamResponse }) {
  return (
    <View style={styles.feedHead}>
      <View style={styles.flex}>
        <Text variant="captionStrong" color={colors.muted}>
          {stream.generatedAt ? `更新于 ${formatTime(stream.generatedAt)}` : "今日结论"}
        </Text>
        <Text variant="small" color={colors.muted} style={styles.feedStats}>
          复核 {stream.stats.total} 场 · 过三关 {stream.stats.promoted} 场 · 复核中 {stream.stats.screening} 场
        </Text>
      </View>
    </View>
  );
}

export function RestDayCard({ rest, onOpenLedger }: { rest: RestDay; onOpenLedger: () => void }) {
  return (
    <Card style={styles.block}>
      <View style={styles.blockHead}>
        <View style={styles.iconCircle}><Icon name="moon-outline" size={18} color={colors.green} /></View>
        <Text variant="bodyStrong" style={styles.flex}>今天没有竞彩足球场次</Text>
      </View>
      <Text variant="small" color={colors.muted} style={styles.paragraph}>{rest.message}</Text>
      {rest.course.title ? (
        <View style={styles.lesson}>
          <Text variant="captionStrong" color={colors.green}>2 分钟 · {rest.course.title}</Text>
          <Text variant="small" style={styles.paragraph}>{rest.course.body}</Text>
        </View>
      ) : null}
      <Button label="看公开账本" variant="secondary" size="sm" onPress={onOpenLedger} style={styles.blockAction} />
    </Card>
  );
}

export function EmptyDayCard({
  copyTitle,
  copyBody,
  onYesterday,
  onOnSale,
}: {
  copyTitle: string;
  copyBody: string;
  onYesterday: () => void;
  onOnSale: () => void;
}) {
  return (
    <Card style={styles.block}>
      <Text variant="h3">{copyTitle}</Text>
      <Text variant="small" color={colors.muted} style={styles.paragraph}>{copyBody}</Text>
      <View style={styles.rowActions}>
        <Button label="看昨日复盘" variant="secondary" size="sm" onPress={onYesterday} style={styles.flex} />
        <Button label="今日在售" variant="primary" size="sm" onPress={onOnSale} style={styles.flex} />
      </View>
    </Card>
  );
}

export function AvoidSection({
  items,
  onOpen,
}: {
  items: AvoidItem[];
  onOpen: (matchId: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        <Text variant="h3">今天不碰</Text>
        <Text variant="caption" color={colors.muted}>死因完全公开</Text>
      </View>
      <Card padded={false}>
        {items.map((item, index) => {
          const tone = gateTone(item.gate === "price" || item.gate === "market" || item.gate === "model" ? "fail" : "unknown");
          return (
            <Pressable
              key={item.verdictId}
              onPress={() => onOpen(item.matchId)}
              accessibilityRole="button"
              accessibilityLabel={`${item.home} 对 ${item.away}，${item.why}`}
              style={({ pressed }) => [
                styles.avoidRow,
                index < items.length - 1 && styles.rowLine,
                pressed && styles.pressed,
              ]}
            >
              <View style={[styles.gateDot, { backgroundColor: tone.color }]} />
              <View style={styles.flex}>
                <Text variant="smallStrong" numberOfLines={1}>
                  {item.home} <Text variant="caption" color={colors.muted}>vs</Text> {item.away}
                </Text>
                <Text variant="caption" color={colors.muted} numberOfLines={1}>{item.why}</Text>
              </View>
              <Chip label={item.gate === "price" ? "价" : item.gate === "market" ? "市" : "模"} tone="danger" />
            </Pressable>
          );
        })}
      </Card>
    </View>
  );
}

export function PostmortemSection({
  items,
  onOpen,
}: {
  items: PostmortemSummary[];
  onOpen: (verdictId: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        <Text variant="h3">最近复盘</Text>
        <Text variant="caption" color={colors.muted}>输赢都写</Text>
      </View>
      <Card padded={false}>
        {items.map((item, index) => (
          <Pressable
            key={item.verdictId}
            onPress={() => onOpen(item.verdictId)}
            accessibilityRole="button"
            accessibilityLabel={`${item.match} 复盘`}
            style={({ pressed }) => [
              styles.avoidRow,
              index < items.length - 1 && styles.rowLine,
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.flex}>
              <Text variant="smallStrong">{item.match}</Text>
              <Text variant="caption" color={colors.muted}>
                {item.resultScore ?? "待结算"} · {item.attribution ?? "未归因"}
              </Text>
            </View>
            <Text variant="captionStrong" color={item.settled === "win" ? colors.green : colors.danger}>
              {item.settled === "win" ? "✓ 中" : item.settled === "lose" ? "× 未中" : "待定"}
            </Text>
          </Pressable>
        ))}
      </Card>
    </View>
  );
}

export function DataStatusSheet({
  visible,
  onClose,
  stream,
}: {
  visible: boolean;
  onClose: () => void;
  stream: StreamResponse | null;
}) {
  const marketPending = stream?.watch.some((v) => v.gates.market === "pending_data") ?? false;
  const modelPending = stream?.watch.some((v) => v.gates.model === "pending_data") ?? false;
  const rows = [
    { name: "竞彩官方 SP", status: "已接入", ok: true },
    { name: "国际盘口", status: marketPending ? "部分未覆盖" : "已接入", ok: !marketPending },
    { name: "xG 强度模型", status: modelPending ? "部分未覆盖" : "已接入", ok: !modelPending },
    { name: "赛程 / 停售", status: "已同步", ok: true },
  ];
  return (
    <Sheet visible={visible} onClose={onClose} title="数据状态" subtitle="每条判断都带来源与截止时间。">
      <Text variant="small" color={colors.muted} style={styles.paragraph}>
        {stream?.stats.gateNote || "三关引擎：价=抽水阈值 · 市=多源分歧 · 模=收缩置信。"}
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
        未覆盖的数据不会被编造，相关场次会显示「等数据」。最近更新：
        {stream?.generatedAt ? formatTime(stream.generatedAt) : "待同步"}。
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
  flex: { flex: 1 },
  dateStrip: { gap: spacing.xs, alignItems: "center", paddingVertical: spacing.sm },
  dateLabel: { marginLeft: spacing.xs },
  feedHead: { marginTop: spacing.x4, marginBottom: spacing.xs },
  feedStats: { marginTop: 2 },
  block: { marginTop: spacing.base, gap: spacing.sm },
  blockHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  iconCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  paragraph: { lineHeight: 20 },
  lesson: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    padding: spacing.base,
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  blockAction: { alignSelf: "flex-start", marginTop: spacing.xs },
  rowActions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  section: { marginTop: spacing.x4 },
  sectionHead: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  avoidRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.base,
    minHeight: 56,
  },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { backgroundColor: colors.bgElevated },
  gateDot: { width: 7, height: 7, borderRadius: 4 },
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
  footer: { marginTop: spacing.x4, paddingHorizontal: spacing.x4, lineHeight: 18 },
});
