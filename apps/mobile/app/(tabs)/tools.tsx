import { ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, Chip, Icon, Text } from "@/components/ui";
import type { IconName } from "@/components/ui";
import { useStreamQuery } from "@/features/home/queries";
import { usePersonaContent } from "@/features/personas/usePersona";
import { currentTradeDateCn } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";

interface Tool {
  key: string;
  title: string;
  subtitle: string;
  icon: IconName;
  route: string;
}

const TOOLS: Tool[] = [
  { key: "parlay", title: "串关体检", subtitle: "多腿组合的返还率与期望", icon: "git-merge-outline", route: "/tools/parlay" },
  { key: "rake", title: "抽水计算", subtitle: "三向赔率 → 真实抽水", icon: "water-outline", route: "/tools/rake" },
  { key: "odds", title: "赔率换算", subtitle: "欧 / 港 / 印尼 / 美式", icon: "swap-horizontal-outline", route: "/tools/odds" },
  { key: "stake", title: "仓位计算", subtitle: "凯利分数与单注上限", icon: "stats-chart-outline", route: "/tools/stake" },
  { key: "breakeven", title: "回本线", subtitle: "这个赔率要赢多少才不亏", icon: "analytics-outline", route: "/tools/break-even" },
  { key: "onsale", title: "今日在售", subtitle: "停售时间与过闸状态", icon: "calendar-outline", route: "/tools/on-sale" },
  { key: "whynot", title: "为什么不推", subtitle: "死在哪一关，全部公开", icon: "close-circle-outline", route: "/tools/why-not" },
  { key: "ledger", title: "公开账本", subtitle: "全部结论与连败都在", icon: "book-outline", route: "/records/ledger" },
];

export default function ToolsScreen() {
  const router = useRouter();
  const { copy } = usePersonaContent();
  const streamQuery = useStreamQuery(currentTradeDateCn());
  const stream = streamQuery.data?.pages[0];
  const stats = stream?.stats;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="工具箱"
        subtitle="解球 · AI 助理"
        onAssistantPress={() => router.push("/assistant")}
        right={<Chip label="8 个工具" tone="green" />}
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Text variant="overline" color={colors.green}>工具</Text>
        <Text variant="display" style={styles.title}>把账算清楚。</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          拍票、比价、体检、复盘。每个工具只回答一个问题：这笔钱花得值不值。
        </Text>

        <View style={styles.grid}>
          {TOOLS.map((tool) => (
            <ToolTile
              key={tool.key}
              tool={tool}
              onPress={() => router.push(tool.route as never)}
            />
          ))}
        </View>

        <Card style={styles.summary}>
          <View style={styles.summaryHead}>
            <View style={styles.flex}>
              <Text variant="overline" color={colors.green}>今日数据</Text>
              <Text variant="h3">{stats ? `复核 ${stats.total} 场` : "正在同步今日场次"}</Text>
            </View>
            <Icon name="pulse-outline" size={20} color={colors.green} />
          </View>
          <View style={styles.metricsRow}>
            <Metric label="过三关" value={String(stats?.promoted ?? 0)} />
            <Metric label="复核中" value={String(stats?.screening ?? 0)} />
            <Metric label="已砍" value={String(stats?.priceFail ?? 0)} />
          </View>
          <Text variant="caption" color={colors.muted} style={styles.summaryNote}>
            {copy.whyNotLead}
          </Text>
        </Card>

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          所有计算只处理赔率与概率，不构成投注建议。{copy.footer}
        </Text>
      </ScrollView>
    </AppScreen>
  );
}

function ToolTile({ tool, onPress }: { tool: Tool; onPress: () => void }) {
  return (
    <Card onPress={onPress} accessibilityLabel={tool.title} style={styles.tile}>
      <View style={styles.tileIcon}>
        <Icon name={tool.icon} size={19} color={colors.green} />
      </View>
      <Text variant="bodyStrong" style={styles.tileTitle}>{tool.title}</Text>
      <Text variant="caption" color={colors.muted} numberOfLines={2} style={styles.tileSub}>
        {tool.subtitle}
      </Text>
      <Icon name="arrow-forward" size={14} color={colors.subtle} style={styles.tileArrow} />
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text variant="h2">{value}</Text>
      <Text variant="caption" color={colors.muted}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: spacing.md,
    marginTop: spacing.x4,
  },
  tile: {
    width: "48.4%",
    minHeight: 140,
    padding: spacing.base,
    gap: 3,
    marginTop: 0,
  },
  tileIcon: {
    width: 34,
    height: 34,
    borderRadius: radii.sm,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  tileTitle: { fontSize: 15 },
  tileSub: { lineHeight: 17 },
  tileArrow: { position: "absolute", right: spacing.base, top: spacing.base },
  summary: { marginTop: spacing.x4, gap: spacing.sm },
  summaryHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  flex: { flex: 1, gap: 1 },
  metricsRow: { flexDirection: "row", gap: spacing.x4 },
  metric: { gap: 0 },
  summaryNote: { lineHeight: 18 },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
});
