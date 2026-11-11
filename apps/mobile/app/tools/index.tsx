import { ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { goBackOr } from "@/lib/navigation";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, Icon, SettingsGroup, SettingsRow, Text } from "@/components/ui";
import type { IconName } from "@/components/ui";
import { useHideFloatingOnScroll } from "@/features/assistant/useHideFloatingOnScroll";
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
  { key: "parlay", title: "串关参谋", subtitle: "从预测生成组合，或自己体检", icon: "git-merge-outline", route: "/tools/parlay" },
  { key: "rake", title: "抽水计算", subtitle: "三向赔率 → 真实抽水", icon: "water-outline", route: "/tools/rake" },
  { key: "odds", title: "赔率换算", subtitle: "欧 / 港 / 印尼 / 美式", icon: "swap-horizontal-outline", route: "/tools/odds" },
  { key: "stake", title: "仓位计算", subtitle: "凯利分数与单注上限", icon: "stats-chart-outline", route: "/tools/stake" },
  { key: "breakeven", title: "回本线", subtitle: "这个赔率要赢多少才不亏", icon: "analytics-outline", route: "/tools/break-even" },
  { key: "whynot", title: "为什么不出", subtitle: "没给预测的场次，原因全公开", icon: "close-circle-outline", route: "/tools/why-not" },
];

export default function ToolsScreen() {
  const router = useRouter();
  const { copy } = usePersonaContent();
  const onScroll = useHideFloatingOnScroll();
  const streamQuery = useStreamQuery(currentTradeDateCn());
  const stream = streamQuery.data?.pages[0];
  const stats = stream?.stats;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="助理技能"
        subtitle="球多多 · 计算与体检"
        showAssistant={false}
        onBack={() => goBackOr(router)}
        right={<Text variant="caption" color={colors.muted}>{TOOLS.length} 个工具</Text>}
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        onScroll={onScroll}
        scrollEventThrottle={48}
      >
        <Text variant="overline" color={colors.green}>工具</Text>
        <Text variant="display" style={styles.title}>把预测看透</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          预测之后，用这些工具把成本、仓位、组合和复盘算清楚。
        </Text>

        <Card
          tone="green"
          onPress={() => router.push(TOOLS[0].route as never)}
          accessibilityLabel="串关参谋"
          style={styles.feature}
        >
          <View style={styles.featureIcon}>
            <Icon name={TOOLS[0].icon} size={22} color={colors.green} />
          </View>
          <View style={styles.featureText}>
            <Text variant="overline" color={colors.green}>主工具</Text>
            <Text variant="h2">{TOOLS[0].title}</Text>
            <Text variant="small" color={colors.muted}>{TOOLS[0].subtitle}</Text>
          </View>
          <Icon name="arrow-forward" size={18} color={colors.green} />
        </Card>

        <View style={styles.groups}>
          <SettingsGroup title="计算工具">
            {TOOLS.slice(1, 5).map((tool, index) => (
              <SettingsRow
                key={tool.key}
                title={tool.title}
                subtitle={tool.subtitle}
                icon={tool.icon}
                onPress={() => router.push(tool.route as never)}
                last={index === 3}
              />
            ))}
          </SettingsGroup>

          <SettingsGroup title="看比赛">
            {TOOLS.slice(5).map((tool) => (
              <SettingsRow
                key={tool.key}
                title={tool.title}
                subtitle={tool.subtitle}
                icon={tool.icon}
                onPress={() => router.push(tool.route as never)}
                last
              />
            ))}
          </SettingsGroup>
        </View>

        <Card style={styles.summary}>
          <View style={styles.summaryHead}>
            <View style={styles.flex}>
              <Text variant="overline" color={colors.green}>今日数据</Text>
              <Text variant="h3">{stats ? `扫描 ${stats.total} 场` : "正在同步今日场次"}</Text>
            </View>
            <Icon name="pulse-outline" size={20} color={colors.green} />
          </View>
          <View style={styles.metricsRow}>
            <Metric label="通过三关" value={String(stats?.promoted ?? 0)} />
            <Metric label="复核中" value={String(stats?.screening ?? 0)} />
            <Metric label="未出预测" value={String(stats?.priceFail ?? 0)} />
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
  feature: {
    marginTop: spacing.x4,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
  },
  featureIcon: {
    width: 44,
    height: 44,
    borderRadius: radii.sm,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  featureText: { flex: 1, gap: 1 },
  groups: { marginTop: spacing.x4, gap: spacing.x4 },
  summary: { marginTop: spacing.x4, gap: spacing.sm },
  summaryHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  flex: { flex: 1, gap: 1 },
  metricsRow: { flexDirection: "row", gap: spacing.x4 },
  metric: { gap: 0 },
  summaryNote: { lineHeight: 18 },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
});
