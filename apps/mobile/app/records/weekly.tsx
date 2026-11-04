import { useState } from "react";
import { Share, ScrollView, StyleSheet, View } from "react-native";
import { goBackOr } from "@/lib/navigation";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, EmptyState, ErrorState, ProgressBar, Skeleton, Text, useToast } from "@/components/ui";
import { useWeeklyQuery } from "@/features/records/queries";
import { useAuthStore } from "@/features/auth/authStore";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { errorText } from "@/lib/errors";
import { money, pct, signedMoney } from "@/lib/format";
import { colors, layout, spacing } from "@/theme/tokens";

export default function WeeklyScreen() {
  const router = useRouter();
  const toast = useToast();
  const session = useAuthStore((s) => s.session);
  const query = useWeeklyQuery(Boolean(session));
  const report = query.data;
  const [sharing, setSharing] = useState(false);

  const share = async () => {
    if (!session || sharing) return;
    setSharing(true);
    try {
      const card = await callApi(
        api.client.POST("/share/weekly"),
      ) as { text: string; url: string; deep_link: string };
      const web = card.url.startsWith("http")
        ? card.url
        : `${api.baseUrl.replace(/\/$/, "")}${card.url}`;
      await Share.share({ message: `${card.text}\n${web}\n${card.deep_link}` });
    } catch (e) {
      toast.show(errorText(e), "error");
    } finally {
      setSharing(false);
    }
  };

  const attribution = Object.entries(report?.attribution ?? {});
  const maxAttr = Math.max(1, ...attribution.map(([, n]) => n));

  return (
    <AppScreen bottom={false}>
      <AppHeader title="周报" showAssistant={false} onBack={() => goBackOr(router)} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {query.isLoading ? (
          <Skeleton height={260} radius={20} />
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : !report ? (
          <EmptyState title="周报还没生成" body="等第一批结算出来，这里只讲事实。" />
        ) : (
          <>
            <Card tone="green" style={styles.hero}>
              <Text variant="overline" color={colors.green}>近 {report.rangeDays} 天</Text>
              <Text variant="display" style={styles.heroTitle}>
                {report.settled > 0 ? `${report.wins} / ${report.settled}` : "等待赛果"}
              </Text>
              <Text variant="small" color={colors.muted}>已结算命中 / 已结算</Text>
              <View style={styles.heroMeta}>
                <Mini label="复核" value={String(report.verdictsTotal)} />
                <Mini label="过三关" value={String(report.promoted)} />
                <Mini label="已结算" value={String(report.settled)} />
              </View>
            </Card>

            {report.you ? (
              <Card style={styles.block}>
                <Text variant="h3">你的账</Text>
                <View style={styles.youRow}>
                  <Mini label="本周注数" value={String(report.you.bets)} />
                  <Mini label="已结算" value={String(report.you.settledBets)} />
                  <Mini
                    label="盈亏"
                    value={signedMoney(report.you.pnl)}
                    tone={report.you.pnl >= 0 ? "green" : "danger"}
                  />
                </View>
                <Text variant="caption" color={colors.muted} style={styles.note}>
                  只统计真实记入的注单，不含任何模拟收益。
                </Text>
              </Card>
            ) : null}

            <Card style={styles.block}>
              <Text variant="h3">归因分布</Text>
              {attribution.length === 0 ? (
                <Text variant="small" color={colors.muted}>还没有已结算的样本可归因。</Text>
              ) : (
                attribution.map(([label, count]) => (
                  <View key={label} style={styles.attrRow}>
                    <View style={styles.attrHead}>
                      <Text variant="small">{label}</Text>
                      <Text variant="smallStrong">{count}</Text>
                    </View>
                    <ProgressBar value={count / maxAttr} height={5} />
                  </View>
                ))
              )}
              <Text variant="caption" color={colors.muted} style={styles.note}>
                归因是确定性的：随机波动、信息不足、强判断落空、高置信落空、判断兑现，都能回放。
              </Text>
            </Card>

            <Card style={styles.block}>
              <Text variant="h3">砍掉的场，后来怎样了</Text>
              <View style={styles.killedRow}>
                <Mini label="砍掉" value={String(report.killed.killedTotal)} />
                <Mini label="砍对" value={String(report.killed.wouldLose)} tone="green" />
                <Mini label="砍错" value={String(report.killed.wouldWin)} tone="danger" />
              </View>
              <View style={styles.moneyRow}>
                <Text variant="caption" color={colors.muted}>避免损失</Text>
                <Text variant="bodyStrong" color={colors.green}>{money(report.killed.avoidedLossCny)}</Text>
                <Text variant="caption" color={colors.muted}>错过机会</Text>
                <Text variant="bodyStrong" color={colors.danger}>{money(report.killed.missedWinCny)}</Text>
              </View>
              <Text variant="caption" color={colors.muted} style={styles.note}>
                两面都公开。只讲砍对不讲砍错，是营销，不是账本。
              </Text>
            </Card>

            <Button
              label="分享周报"
              variant="secondary"
              icon="share-social-outline"
              onPress={share}
              disabled={!session}
              fullWidth
            />
            <Text variant="caption" color={colors.subtle} center style={styles.footer}>
              {report.settled > 0
                ? `${pct(report.wins / report.settled)} 是本周期真实结算比例，不代表未来。`
                : "还没有结算样本。等赛果出来，这里只写真实比例。"}
            </Text>
          </>
        )}
      </ScrollView>
    </AppScreen>
  );
}

function Mini({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "green" | "danger";
}) {
  return (
    <View style={styles.mini}>
      <Text variant="caption" color={colors.muted}>{label}</Text>
      <Text variant="h3" color={tone === "green" ? colors.green : tone === "danger" ? colors.danger : colors.ink}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  hero: { gap: spacing.xs },
  heroTitle: { fontSize: 40, lineHeight: 46 },
  heroMeta: { flexDirection: "row", gap: spacing.x4, marginTop: spacing.sm },
  mini: { gap: 2, minWidth: 70 },
  block: { marginTop: spacing.base, gap: spacing.xs },
  youRow: { flexDirection: "row", gap: spacing.x4, marginTop: spacing.xs },
  note: { lineHeight: 18, marginTop: spacing.xs },
  attrRow: { gap: 4, marginTop: spacing.xs },
  attrHead: { flexDirection: "row", justifyContent: "space-between" },
  killedRow: { flexDirection: "row", gap: spacing.x4, marginTop: spacing.xs },
  moneyRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.sm, alignItems: "baseline" },
  footer: { marginTop: spacing.base, lineHeight: 18 },
});
