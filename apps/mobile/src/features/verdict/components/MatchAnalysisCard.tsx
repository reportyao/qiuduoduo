import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Button, Card, Skeleton, Text } from "@/components/ui";
import {
  useGenerateMatchAnalysisMutation,
  useMatchAnalysisQuery,
} from "@/features/verdict/queries";
import { formatDateTime } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

interface Props {
  matchId: string;
  date: string;
}

function Bullets({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <View style={styles.block}>
      <Text variant="captionStrong" color={colors.muted}>{label}</Text>
      {items.map((item, index) => (
        <Text key={`${label}-${index}`} variant="small" color={colors.ink} style={styles.line}>
          · {item}
        </Text>
      ))}
    </View>
  );
}

/**
 * 单场 AI 解读：只展示后端已生成并缓存的内容。
 * 未生成时由用户显式触发；数据不足/模型未配置时如实说明，不拿模板冒充解读。
 */
export function MatchAnalysisCard({ matchId, date }: Props) {
  const query = useMatchAnalysisQuery(matchId, date);
  const generate = useGenerateMatchAnalysisMutation();
  const analysis = query.data;

  if (query.isLoading) {
    return (
      <Card style={styles.card}>
        <Skeleton height={18} width="38%" />
        <Skeleton height={14} style={{ marginTop: spacing.sm }} />
        <Skeleton height={14} width="82%" style={{ marginTop: spacing.xs }} />
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card style={styles.card}>
        <Text variant="h3">AI 解读</Text>
        <Text variant="small" color={colors.muted}>读取失败，稍后再试。</Text>
        <Button label="重试" size="sm" variant="ghost" onPress={() => void query.refetch()} />
      </Card>
    );
  }

  if (analysis?.status === "ready") {
    return (
      <Card style={styles.card}>
        <View style={styles.head}>
          <Text variant="h3">AI 解读</Text>
          <Text variant="caption" color={colors.subtle}>
            {analysis.cached ? "缓存" : "刚刚生成"}
            {analysis.generated_at ? ` · ${formatDateTime(analysis.generated_at)}` : ""}
          </Text>
        </View>
        <Text variant="small" color={colors.ink} style={styles.summary}>
          {analysis.summary}
        </Text>
        <Bullets label="关键依据" items={analysis.key_factors} />
        <Bullets label="风险" items={analysis.risks} />
        <Bullets label="失效条件" items={analysis.invalidators} />
        <Bullets label="数据缺口" items={analysis.data_gaps} />
        {analysis.confidence_note ? (
          <Text variant="caption" color={colors.subtle} style={styles.note}>
            {analysis.confidence_note}
          </Text>
        ) : null}
        <Text variant="caption" color={colors.subtle} style={styles.note}>
          只解释已给的数据，不改写概率；数据截止 {analysis.data_cutoff ? formatDateTime(analysis.data_cutoff) : "未知"}。
        </Text>
      </Card>
    );
  }

  const reason = analysis?.reason;
  const missing = analysis?.missing ?? [];
  const canGenerate = reason === "not_generated" || reason === "coverage";
  const unavailableText = reason === "coverage"
    ? `数据还不够，先不生成解读${missing.length ? `（缺 ${missing.join("、")}）` : ""}。`
    : reason === "not_configured"
      ? "AI 解读还没配置 deep 模型；先看三关与数据。"
      : "这场暂时没有可用的 AI 解读。";

  return (
    <Card style={styles.card}>
      <Text variant="h3">AI 解读</Text>
      <Text variant="small" color={colors.muted}>{unavailableText}</Text>
      {canGenerate ? (
        <View style={styles.actions}>
          <Button
            label={generate.isPending ? "生成中…" : "生成 AI 解读"}
            size="sm"
            variant="secondary"
            disabled={generate.isPending}
            onPress={() => generate.mutate({ matchId, date })}
          />
          {generate.isPending ? <ActivityIndicator size="small" color={colors.green} /> : null}
        </View>
      ) : null}
      <Text variant="caption" color={colors.subtle}>
        只对覆盖完整、可深读的场次生成；生成后按数据截止缓存，数据变化会重新计算。
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base, gap: spacing.xs },
  head: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: spacing.sm },
  summary: { lineHeight: 21 },
  block: { marginTop: spacing.xs, gap: 2 },
  line: { lineHeight: 19 },
  note: { lineHeight: 18, marginTop: spacing.xs },
  actions: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm },
});
