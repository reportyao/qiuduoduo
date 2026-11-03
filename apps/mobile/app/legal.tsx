import { ScrollView, StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, Text } from "@/components/ui";
import { useDisclosureQuery, useLegalQuery } from "@/features/account/queries";
import { colors, layout, spacing } from "@/theme/tokens";

const TITLES: Record<string, string> = {
  terms: "服务说明",
  privacy: "隐私政策",
  ai: "数据与 AI 说明",
};

export default function LegalScreen() {
  const router = useRouter();
  const { doc } = useLocalSearchParams<{ doc?: string }>();
  const key = doc === "privacy" || doc === "ai" ? doc : "terms";
  const legal = useLegalQuery();
  const disclosure = useDisclosureQuery();

  return (
    <AppScreen bottom={false}>
      <AppHeader title={TITLES[key]} showAssistant={false} onBack={() => router.back()} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {key === "terms" ? <Terms /> : key === "privacy" ? <Privacy disclosure={disclosure.data} /> : <AiNotice />}

        <Card tone="green" style={styles.help}>
          <Text variant="smallStrong">需要帮助</Text>
          <Text variant="small" color={colors.muted} style={styles.paragraph}>
            {legal.data?.helpline ? `求助热线：${legal.data.helpline}` : "如感到失控，请联系当地心理援助或戒赌热线。"}
          </Text>
          <Text variant="caption" color={colors.muted}>
            未满 {legal.data?.minAge ?? 18} 周岁禁止购买彩票。
          </Text>
        </Card>

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          数据分析结果，不构成投注建议。本页随产品版本更新，最近更新 2026-11。
        </Text>
      </ScrollView>
    </AppScreen>
  );
}

function Terms() {
  return (
    <>
      <Text variant="h2" style={styles.title}>解球是什么</Text>
      <Text variant="body" color={colors.muted} style={styles.paragraph}>
        解球是一个竞彩数据分析工具。它展示抽水、市场概率、模型置信和不确定性，帮助你在下注前把成本算清楚。
      </Text>
      <Section title="不做什么">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          不销售彩票、不代购、不代兑奖、不承诺收益。所有判断都是概率与情景分析，不是结果保证。
        </Text>
      </Section>
      <Section title="判断与封存">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          每条判断在赛前封存 sha256。赛后修订会保留完整历史，不能覆盖旧结论。公开账本同时展示命中与未中。
        </Text>
      </Section>
      <Section title="账号与记录">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          “记一注”只记录金额与选择，不代购。注单默认仅你可见；公开账本不展示个人金额。
        </Text>
      </Section>
      <Section title="年龄与自排除">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          未满 18 周岁只能查看公开账本。自排除生效期间，本机会拦截判断与记录；到期前不可撤销。
        </Text>
      </Section>
    </>
  );
}

function Privacy({ disclosure }: { disclosure?: ReturnType<typeof useDisclosureQuery>["data"] }) {
  return (
    <>
      <Text variant="h2" style={styles.title}>我们收集什么</Text>
      <Card style={styles.block}>
        {(disclosure?.privacy.collects ?? [
          "手机号或邮箱（登录标识）",
          "第三方登录匿名标识",
          "记注金额与选择（仅你可见）",
          "语言 / 人设 / 区域偏好",
        ]).map((item) => (
          <Bullet key={item} text={item} />
        ))}
      </Card>
      <Text variant="h2" style={styles.title}>不收集什么</Text>
      <Card style={styles.block}>
        {(disclosure?.privacy.not_collects ?? [
          "出生日期",
          "真实姓名与身份证",
          "支付凭证",
          "通讯录 / 位置 / 相册",
        ]).map((item) => (
          <Bullet key={item} text={item} />
        ))}
      </Card>
      <Section title="共享与存储">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          {disclosure?.privacy.sharing ??
            "不向第三方共享、不出售。数据可随时导出，注销后 7 天清除。"}
          {"\n"}
          {disclosure?.privacy.storage ??
            "数据存储于中国境内主库；跨境传输按适用法律处理。"}
        </Text>
      </Section>
      <Section title="你的权利">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          你可以在「我的 → 隐私与数据」导出 JSON、删除记忆或注销账号。注销有 7 天冷静期，同一设备登录可撤回。
        </Text>
      </Section>
    </>
  );
}

function AiNotice() {
  return (
    <>
      <Text variant="h2" style={styles.title}>数字从哪来</Text>
      <Text variant="body" color={colors.muted} style={styles.paragraph}>
        概率来自统计模型（Dixon-Coles 等）与市场去水。AI 负责把结构化数据解释成人话、组织反方情景，
        不负责“编一个概率”。模型与市场未覆盖的维度，会明确显示「未覆盖」。
      </Text>
      <Section title="误差与边界">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          概率有误差，单场结果随机。54% 不是“稳”，买十次约对五次，连错三次也正常。
          AI 情景分析不保证命中，也不改变封存里的数字。
        </Text>
      </Section>
      <Section title="人设只改语气">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          理性专家、感性老炮、萌妹萝莉只影响说话方式，不影响概率、三关状态、封存内容与合规提示。
        </Text>
      </Section>
      <Section title="数据截止">
        <Text variant="body" color={colors.muted} style={styles.paragraph}>
          每条依据都有来源和截止时间。首发公布后若关键数据变化，结论会重算并生成新修订，旧版本保留。
        </Text>
      </Section>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text variant="h3">{title}</Text>
      {children}
    </View>
  );
}

function Bullet({ text }: { text: string }) {
  return (
    <View style={styles.bullet}>
      <View style={styles.dot} />
      <Text variant="small" color={colors.muted} style={styles.bulletText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.x4, marginBottom: spacing.sm },
  section: { marginTop: spacing.x4, gap: spacing.xs },
  paragraph: { lineHeight: 22 },
  block: { gap: spacing.sm },
  bullet: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.green, marginTop: 8 },
  bulletText: { flex: 1, lineHeight: 19 },
  help: { marginTop: spacing.x4, gap: spacing.xs },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
});
