import { StyleSheet } from "react-native";
import type { GateKey, VerdictDetail } from "@/domain/types";
import { colors, spacing } from "@/theme/tokens";
import { Card, Text } from "@/components/ui";
import { GateDetailRow } from "./Gates";

export function GateDetailsCard({ detail }: { detail: VerdictDetail }) {
  return (
    <Card style={styles.card}>
      <Text variant="h3">三关明细</Text>
      <Text variant="caption" color={colors.muted} style={styles.sub}>
        价 = 抽水是否够浅；市 = 多源口径是否收敛；模 = 收缩后置信是否过线。
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
