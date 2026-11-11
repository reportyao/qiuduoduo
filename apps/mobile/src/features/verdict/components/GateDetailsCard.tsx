import { StyleSheet } from "react-native";
import type { GateKey, VerdictDetail } from "@/domain/types";
import { colors, spacing } from "@/theme/tokens";
import { Card, Text } from "@/components/ui";
import { GateDetailRow } from "./Gates";

export function GateDetailsCard({ detail }: { detail: VerdictDetail }) {
  return (
    <Card style={styles.card}>
      <Text variant="h3">
        {detail.tier === "verified" ? "核验依据" : "数据与风险"}
      </Text>
      <Text variant="caption" color={colors.muted} style={styles.sub}>
        {detail.tier === "market_reference"
          ? "这场没有通过模型验证，只展示市场倾向；下面是数据完整度与风险项。"
          : "价 = 抽水是否够浅；市 = 多源口径是否收敛；模 = 模型置信是否过线。"}
      </Text>
      {(["price", "market", "model"] as GateKey[]).map((gate, index) => (
        <GateDetailRow
          key={gate}
          gate={gate}
          entry={detail.gatesDetail[gate]}
          last={index === 2}
        />
      ))}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base, gap: spacing.xs },
  sub: { lineHeight: 18, marginBottom: spacing.xs },
});
