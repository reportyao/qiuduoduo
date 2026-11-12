import { StyleSheet, View } from "react-native";
import { Card, Text } from "@/components/ui";
import type { AIResearchData } from "@/domain/types";
import { colors, spacing } from "@/theme/tokens";
import { brandCopy } from "@/lib/brand";

/** AI 情报：只展示公开事实的中文摘要，明确“非概率”。 */
export function AiIntelCard({ data }: { data: AIResearchData }) {
  if (data.status !== "ready") return null;
  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <Text variant="h3">AI 情报</Text>
        <Text variant="caption" color={colors.amber}>非概率</Text>
      </View>
      <Text variant="body" color={colors.ink} style={styles.headline}>{brandCopy(data.headline)}</Text>
      {data.points.map((point) => (
        <Text key={point} variant="small" color={colors.muted} style={styles.point}>
          · {brandCopy(point)}
        </Text>
      ))}
      <Text variant="caption" color={colors.subtle} style={styles.note}>
        来源：球多多自研AI引擎预测 · 公开信息摘要，不构成概率预测
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base, gap: spacing.xs },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  headline: { lineHeight: 22 },
  point: { lineHeight: 19 },
  note: { marginTop: spacing.xs, lineHeight: 17 },
});
