import { useEffect } from "react";
import { Image, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button, Card, Text } from "@/components/ui";
import { useComplianceStore } from "@/features/compliance/complianceStore";
import { useLegalQuery } from "@/features/account/queries";
import { formatDate, formatTime } from "@/lib/format";
import { useNow } from "@/lib/useNow";
import { colors, layout, spacing } from "@/theme/tokens";

export default function PausedScreen() {
  const router = useRouter();
  const until = useComplianceStore((s) => s.excludedUntil);
  const permanent = useComplianceStore((s) => s.excludedPermanent);
  const legal = useLegalQuery();
  const now = useNow(60_000);
  const active = permanent || (until != null && until > now);
  const remainingDays = until ? Math.max(0, Math.ceil((until - now) / 86_400_000)) : 0;

  useEffect(() => {
    if (!active) router.replace("/(tabs)");
  }, [active, router]);

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.hero}>
        <Image
          source={require("../assets/mascot/zhuanjia.png")}
          style={styles.avatar}
          resizeMode="cover"
        />
        <Text variant="overline" color={colors.amber}>自排除生效中</Text>
        <Text variant="display" center style={styles.title}>先停一停。</Text>
        <Text variant="body" color={colors.muted} center style={styles.lead}>
          在这段时间里，这台设备不会给你看判断与记录；已登录账号会同步暂停通知。到期前不可撤销。
        </Text>
      </View>

      <Card tone="amber" style={styles.card}>
        <Text variant="caption" color={colors.amber}>{permanent ? "期限" : "结束时间"}</Text>
        <Text variant="h2">
          {permanent
            ? "永久生效"
            : until
              ? `${formatDate(new Date(until))} ${formatTime(new Date(until))}`
              : "—"}
        </Text>
        <Text variant="small" color={colors.muted}>
          {permanent
            ? "永久自排除不会自动恢复；当前为设备级记录，服务端人工解除流程尚未接入。"
            : `还剩约 ${remainingDays} 天。到期后会恢复基础功能，但不会自动恢复营销。`}
        </Text>
      </Card>

      <Card style={styles.card}>
        <Text variant="smallStrong">需要聊聊吗</Text>
        <Text variant="small" color={colors.muted} style={styles.text}>
          {legal.data?.helpline
            ? `可以拨打 ${legal.data.helpline}，或联系你信任的人。`
            : "可以联系当地心理援助热线，或找信任的人聊聊。"}
        </Text>
        <Text variant="caption" color={colors.subtle} style={styles.text}>
          这是保护功能，不是惩罚。当前拦截在本机生效；多设备服务端同步是上线前阻塞项。
        </Text>
      </Card>

      <View style={styles.actions}>
        <Button
          label="了解自排除"
          variant="secondary"
          onPress={() => router.push({ pathname: "/legal", params: { doc: "terms" } })}
          fullWidth
        />
      </View>
      <Text variant="caption" color={colors.subtle} center style={styles.footer}>
        数据分析结果，不构成投注建议。未满 18 周岁禁止购买彩票。
      </Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, paddingHorizontal: layout.pagePadding },
  hero: { alignItems: "center", marginTop: spacing.x4, gap: spacing.xs },
  avatar: { width: 92, height: 92, borderRadius: 46, marginBottom: spacing.base, opacity: 0.9 },
  title: { marginTop: spacing.xs },
  lead: { maxWidth: 320, lineHeight: 22, marginTop: spacing.xs },
  card: { marginTop: spacing.base, gap: spacing.xs },
  text: { lineHeight: 19 },
  actions: { marginTop: spacing.base },
  footer: { marginTop: spacing.base, lineHeight: 17 },
});
