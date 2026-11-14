import { Alert, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Chip, ErrorState, Skeleton, Text } from "@/components/ui";
import { useMembershipQuery } from "@/features/plans/queries";
import { errorText } from "@/lib/errors";
import { goBackOr } from "@/lib/navigation";
import { colors, layout, spacing } from "@/theme/tokens";

const PRODUCTS = [
  {
    tier: "pro",
    name: "Pro · 竞彩版",
    price: "¥499/月 · ¥1,199/季",
    items: ["竞彩胜平负 / 让球", "比分 / 总进球 / 半全场", "每日免费额度解除", "不含 AI 计划"],
    tone: "neutral" as const,
  },
  {
    tier: "max",
    name: "Max · 全市场版",
    price: "¥699/月 · ¥1,699/季",
    items: ["全市场数据（逐项开放）", "AI 计划完整方案", "跨市场串关", "最高优先级提醒"],
    tone: "positive" as const,
  },
];

export default function MembershipScreen() {
  const router = useRouter();
  const me = useMembershipQuery();
  const paid = me.data?.is_paid ?? false;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="会员与权益"
        subtitle="充值暂未开放"
        showAssistant={false}
        onBack={() => goBackOr(router)}
        backLabel="返回"
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {me.isLoading ? (
          <Card style={styles.current}>
            <Skeleton width="40%" height={12} />
            <Skeleton width="30%" height={26} style={styles.skeletonGap} />
            <Skeleton width="70%" height={12} style={styles.skeletonGap} />
          </Card>
        ) : me.isError ? (
          <ErrorState
            message={errorText(me.error)}
            onRetry={() => me.refetch()}
          />
        ) : (
        <Card style={styles.current}>
          <View style={styles.rowBetween}>
            <View>
              <Text variant="caption" color={colors.muted}>当前会员</Text>
              <Text variant="h2">{me.data?.tier === "max" ? "Max" : me.data?.tier === "pro" ? "Pro" : "免费"}</Text>
            </View>
            <Chip label={paid ? "已开通" : "未开通"} tone={paid ? "positive" : "neutral"} />
          </View>
          {me.data?.expires_at ? (
            <Text variant="caption" color={colors.muted}>有效期至 {me.data.expires_at.slice(0, 10)}</Text>
          ) : null}
          {me.data?.quota ? (
            <Text variant="caption" color={colors.muted}>
              今日分析额度：{me.data.quota.limit == null ? "不限" : `已用 ${me.data.quota.used} / ${me.data.quota.limit}`}
            </Text>
          ) : null}
          <Text variant="caption" color={colors.subtle}>
            会员权益与额度已生效；充值按钮仅为 UI 预览，不会产生订单或扣款。
          </Text>
        </Card>
        )
      }

        {PRODUCTS.map((product) => (
          <Card key={product.tier} style={styles.product}>
            <View style={styles.rowBetween}>
              <Text variant="h3">{product.name}</Text>
              <Chip label={product.tier === "max" ? "推荐" : "竞彩"} tone={product.tone} />
            </View>
            <Text variant="h2">{product.price}</Text>
            <View style={styles.items}>
              {product.items.map((item) => (
                <Text key={item} variant="small" color={colors.muted}>· {item}</Text>
              ))}
            </View>
            <Button
              label={me.data?.tier === product.tier ? "当前方案" : product.tier === "max" ? "选择 Max" : "选择 Pro"}
              variant={product.tier === "max" ? "primary" : "secondary"}
              disabled={me.data?.tier === product.tier}
              onPress={() => Alert.alert("充值暂未开放", "当前会员由运营后台手动开通。充值支付会在后续版本接入。")}
              fullWidth
            />
          </Card>
        ))}

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          会员仅影响内容与数据权限，不构成投注建议；未满 18 周岁禁止购彩。
        </Text>
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7, gap: spacing.base },
  current: { gap: spacing.xs },
  skeletonGap: { marginTop: spacing.sm },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  product: { gap: spacing.sm },
  items: { gap: 2 },
  footer: { marginTop: spacing.sm, lineHeight: 18 },
});
