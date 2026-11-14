import Constants from "expo-constants";
import { goBackOr } from "@/lib/navigation";
import { StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import {
  Card,
  KeyValueRow,
  SettingsGroup,
  SettingsRow,
  Text,
} from "@/components/ui";
import { useAppVersionQuery, useLegalQuery, useMeQuery } from "@/features/account/queries";
import { colors, spacing } from "@/theme/tokens";

export default function AboutScreen() {
  const router = useRouter();
  const version = useAppVersionQuery();
  const me = useMeQuery();
  const legal = useLegalQuery(me.data?.region ?? "cn");

  return (
    <SettingsPage title="关于球多多" subtitle="赛前预测，有依据" onBack={() => goBackOr(router)}>
      <Card tone="positive">
        <Text variant="h2">球多多</Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          面向竞彩用户的赛前预测助理。给出方向、预测概率、依据与失效条件，也把这一注的成本和不确定性算清楚。
          没有把握的场次，就不发预测。
        </Text>
        <Text variant="caption" color={colors.brand} style={styles.slogan}>
          看得准才说，看不准就不发。
        </Text>
      </Card>

      <Card style={styles.block}>
        <Text variant="overline" color={colors.brand}>版本</Text>
        <KeyValueRow label="App" value={Constants.expoConfig?.version ?? "0.1.0"} />
        <KeyValueRow label="API" value={version.data?.api ?? "连接中"} />
        <KeyValueRow label="最低 App 版本" value={version.data?.min_app_version ?? "—"} last />
      </Card>

      <Card style={styles.block}>
        <Text variant="overline" color={colors.brand}>数据与预测</Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          价格来自竞彩官方 SP；国际盘与 xG 模型按覆盖情况接入。每个数字都带截止时间，
          未覆盖的维度会明确写「未覆盖」，不会补编。
        </Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          预测赛前封存 sha256，赛后不改。输赢与连败都在公开账本里。
        </Text>
        <KeyValueRow label="合规最低年龄" value={`${legal.data?.minAge ?? 18} 周岁`} />
        <KeyValueRow label="数据来源" value={legal.data?.dataSource || "竞彩官方 / 公开数据源"} last />
      </Card>

      <SettingsGroup title="法律与隐私">
        <SettingsRow title="服务说明" icon="document-text-outline" onPress={() => router.push({ pathname: "/legal", params: { doc: "terms" } })} />
        <SettingsRow title="隐私政策" icon="lock-closed-outline" onPress={() => router.push({ pathname: "/legal", params: { doc: "privacy" } })} />
        <SettingsRow title="数据与 AI 说明" icon="sparkles-outline" onPress={() => router.push({ pathname: "/legal", params: { doc: "ai" } })} last />
      </SettingsGroup>

      <Text variant="caption" color={colors.subtle} center style={styles.footer}>
        数据分析结果，不构成投注建议。未满 18 周岁禁止购彩。
      </Text>
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  block: { gap: spacing.xs },
  paragraph: { lineHeight: 20 },
  slogan: { marginTop: spacing.sm },
  footer: { lineHeight: 18, paddingHorizontal: spacing.base },
});
