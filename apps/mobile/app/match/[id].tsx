import { useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { ScrollView, StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Chip, Skeleton, Text } from "@/components/ui";
import { useWhyNotQuery } from "@/features/verdict/queries";
import { usePersonaContent } from "@/features/personas/usePersona";
import { ApiError, errorText } from "@/lib/errors";
import { currentTradeDateCn, formatDate, gateLabel, shortHash } from "@/lib/format";
import { isRecord, string } from "@/lib/parse";
import { colors, layout, spacing } from "@/theme/tokens";
import type { GateKey } from "@/domain/types";
import { gateTone } from "@/features/verdict/components/Gates";
import { GateDetailRow } from "@/features/verdict/components/Gates";

export default function WhyNotScreen() {
  const { id, date } = useLocalSearchParams<{ id: string; date?: string }>();
  const router = useRouter();
  const { copy } = usePersonaContent();
  const query = useWhyNotQuery(id, date || currentTradeDateCn(), true);
  const [logsOpen, setLogsOpen] = useState(false);
  const data = query.data;

  const notFound = query.error instanceof ApiError && query.error.status === 404;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title={data?.verdictKind === "pending" ? "为什么还不出" : "为什么不出"}
        subtitle={data?.league || "判决复核"}
        showAssistant={false}
        onBack={() => goBackOr(router)}
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {query.isLoading ? (
          <>
            <Skeleton height={210} radius={26} />
            <Skeleton height={180} radius={20} style={{ marginTop: spacing.base }} />
            <Skeleton height={150} radius={20} style={{ marginTop: spacing.base }} />
          </>
        ) : query.isError || !data ? (
          <Card style={styles.emptyCard}>
            <Text variant="h3">{notFound ? "这场没有预测记录" : "暂时取不到原因"}</Text>
            <Text variant="small" color={colors.muted} style={styles.paragraph}>
              {notFound
                ? "可能还没进复核池，或数据尚未同步。没有记录就不编原因。"
                : errorText(query.error)}
            </Text>
            <View style={styles.row}>
              <Button label="今日在售" variant="primary" onPress={() => router.push("/tools/on-sale")} style={styles.flex} />
              <Button label="重试" variant="secondary" onPress={() => query.refetch()} style={styles.flex} />
            </View>
          </Card>
        ) : data.status === "promoted" ? (
          <Card style={styles.emptyCard}>
            <Chip label="三关全过" tone="green" />
            <Text variant="h2" style={styles.promotedTitle}>{data.home} vs {data.away}</Text>
            <Text variant="small" color={colors.muted} style={styles.paragraph}>
              这场已经有三关通过的预测，不该出现在「为什么不出」里。直接看完整预测。
            </Text>
            <Button
              label="看完整预测"
              onPress={() =>
                data.verdictId
                  ? router.push({ pathname: "/verdict/[id]", params: { id: data.verdictId } })
                  : router.push("/tools/on-sale")
              }
              fullWidth
            />
          </Card>
        ) : (
          <>
            <Card style={[styles.hero, data.verdictKind === "fail" ? styles.failHero : styles.pendingHero]}>
              <View style={styles.heroHead}>
                <Chip
                  label={data.verdictKind === "pending" ? "预测复核中" : "未给预测"}
                  tone={data.verdictKind === "pending" ? "amber" : "danger"}
                />
                <Text variant="caption" color={colors.muted}>
                  {data.matchNo} · 竞彩日 {formatDate(date)}
                </Text>
              </View>
              <Text variant="h2" style={styles.match}>{data.home} <Text variant="body" color={colors.muted}>vs</Text> {data.away}</Text>
              <Text variant="h3" style={styles.title}>{friendlyTitle(data)}</Text>
              <Text variant="small" color={colors.muted} style={styles.paragraph}>
                {data.verdictKind === "pending"
                  ? "不是不给预测，是还在等关键数据。数据齐了会自动重评，不会悄悄放行。"
                  : "这道闸没过，所以暂时不给预测。下面把每一层原因都摊开。"}
              </Text>
            </Card>

            <Card style={styles.block}>
              <Text variant="h3">三关为什么没过</Text>
              {(["price", "market", "model"] as GateKey[]).map((gate, index) => {
                const raw = isRecord(data.gates[gate]) ? data.gates[gate] : {};
                return (
                  <GateDetailRow
                    key={gate}
                    gate={gate}
                    entry={{
                      gate,
                      result: string(raw.result) === "fail" ? "fail" : string(raw.result) === "pending_data" ? "pending_data" : string(raw.result) === "pass" ? "pass" : "unknown",
                      detail: isRecord(raw.detail) ? raw.detail : {},
                    }}
                    last={index === 2}
                  />
                );
              })}
            </Card>

            <Card style={styles.block}>
              <Text variant="h3">什么时候会重新进池</Text>
              <View style={styles.reentry}>
                <View style={[styles.dot, { backgroundColor: data.verdictKind === "pending" ? colors.amber : colors.green }]} />
                <Text variant="small" style={styles.paragraph}>{data.whatIf || "数据条件满足后自动重评。"}</Text>
              </View>
              <Text variant="caption" color={colors.subtle} style={styles.paragraph}>
                {copy.whyNotLead}
              </Text>
            </Card>

            {data.modelRuns.length > 0 ? (
              <Card style={styles.block}>
                <View style={styles.logHead}>
                  <Text variant="h3">技术附录</Text>
                  <Button
                    label={logsOpen ? "收起" : "查看引擎日志"}
                    variant="ghost"
                    size="sm"
                    onPress={() => setLogsOpen((open) => !open)}
                  />
                </View>
                {logsOpen
                  ? data.modelRuns.map((run, index) => (
                      <View key={`${run.gate}-${index}`} style={styles.logRow}>
                        <Text variant="captionStrong" color={gateTone(run.result === "fail" ? "fail" : run.result === "pass" ? "pass" : "unknown").color}>
                          {gateLabel(run.gate)}闸 · {run.result === "pass" ? "通过" : run.result === "fail" ? "未通过" : "等数据"}
                        </Text>
                        <Text variant="caption" color={colors.muted} numberOfLines={2} style={styles.flex}>
                          {humanRunDetail(run.detail)}
                        </Text>
                      </View>
                    ))
                  : (
                    <Text variant="caption" color={colors.muted}>
                      技术审计信息，日常可以不看。判决哈希 {shortHash(data.verdictHash, 10, 6)} 可独立复算。
                    </Text>
                  )}
              </Card>
            ) : null}

            <View style={styles.actions}>
              <Button label="看今日在售" onPress={() => router.push("/tools/on-sale")} fullWidth />
              <Button label="看已过三关" variant="secondary" onPress={() => router.push("/(tabs)")} fullWidth />
            </View>
            <Text variant="caption" color={colors.subtle} center style={styles.footer}>
              不出预测 ≠ 不会赢。今晚没给预测的场里，约有一部分会朝「本可以发布」的方向走 —— 但算不清是哪一场。算不清就不预测。
            </Text>
          </>
        )}
      </ScrollView>
    </AppScreen>
  );
}


function friendlyTitle(data: {
  verdictKind: "fail" | "pending" | null;
  deadGate: GateKey | null;
}): string {
  if (data.verdictKind === "pending") {
    if (data.deadGate === "market") return "预测复核中 · 等国际盘数据";
    if (data.deadGate === "model") return "预测复核中 · 等模型数据";
    return "预测复核中 · 数据还没齐";
  }
  if (data.deadGate === "price") return "没给预测 · 抽水超过阈值";
  if (data.deadGate === "market") return "没给预测 · 多源分歧过大";
  if (data.deadGate === "model") return "没给预测 · 预测置信不足";
  return "这场暂时没有预测";
}

function humanRunDetail(detail: Record<string, unknown>): string {
  if (typeof detail.reason === "string") return detail.reason;
  if (typeof detail.rake === "number") {
    return `抽水 ${(detail.rake * 100).toFixed(1)}% / 阈值 ${
      typeof detail.threshold === "number" ? (detail.threshold * 100).toFixed(1) + "%" : "待同步"
    }`;
  }
  if (typeof detail.rule === "string") return detail.rule;
  return "已记录，无额外说明";
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.sm, paddingBottom: spacing.x7 },
  flex: { flex: 1 },
  hero: { gap: spacing.xs },
  failHero: { borderColor: colors.dangerSoft },
  pendingHero: { borderColor: colors.amberLine, backgroundColor: colors.surface },
  heroHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  match: { marginTop: spacing.sm },
  title: { marginTop: spacing.sm, lineHeight: 25 },
  paragraph: { lineHeight: 20 },
  block: { marginTop: spacing.base, gap: spacing.xs },
  reentry: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start", marginTop: spacing.xs },
  dot: { width: 7, height: 7, borderRadius: 4, marginTop: 7 },
  logHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  logRow: {
    flexDirection: "row",
    gap: spacing.base,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  actions: { marginTop: spacing.x4, gap: spacing.sm },
  footer: { marginTop: spacing.x4, lineHeight: 18, paddingHorizontal: spacing.base },
  emptyCard: { gap: spacing.sm },
  promotedTitle: { marginTop: spacing.xs },
  row: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
});
