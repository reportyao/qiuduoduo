import { StyleSheet, View } from "react-native";
import type { GateDetail, GateKey, GateResult } from "@/domain/types";
import { colors, radii, spacing } from "@/theme/tokens";
import { gateDetailText } from "@/features/verdict/gateText";
import { Text } from "@/components/ui";

export function gateTone(result: GateResult | undefined): {
  color: string;
  soft: string;
  label: string;
  short: string;
} {
  switch (result) {
    case "pass":
      return { color: colors.brand, soft: colors.brandSoft, label: "已通过", short: "✓" };
    case "fail":
      return { color: colors.loss, soft: colors.lossSoft, label: "未通过", short: "×" };
    case "pending_data":
      return { color: colors.amber, soft: colors.amberSoft, label: "等数据", short: "…" };
    default:
      return { color: colors.muted, soft: colors.bgElevated, label: "待定", short: "·" };
  }
}

const GATE_LABEL: Record<GateKey, string> = { price: "价", market: "市", model: "模" };

export function GateStrip({
  gates,
  dark = false,
  values,
}: {
  gates: Partial<Record<GateKey, GateResult>>;
  dark?: boolean;
  values?: Partial<Record<GateKey, string>>;
}) {
  return (
    <View style={[styles.strip, dark && styles.stripDark]}>
      {(["price", "market", "model"] as GateKey[]).map((key, index) => {
        const tone = gateTone(gates[key]);
        return (
          <View key={key} style={[styles.cell, index < 2 && (dark ? styles.cellDark : styles.cellLine)]}>
            <View style={styles.cellHead}>
              <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
                {GATE_LABEL[key]}
              </Text>
              <Text variant="captionStrong" color={dark ? tone.soft : tone.color}>
                {tone.label}
              </Text>
            </View>
            <Text variant="smallStrong" color={dark ? colors.inkInverse : colors.ink}>
              {values?.[key] ?? (key === "price" ? "抽水" : key === "market" ? "多源" : "置信")}
            </Text>
          </View>
        );
      })}
    </View>
  );
}


export function GateDetailRow({
  gate,
  entry,
  last = false,
}: {
  gate: GateKey;
  entry?: GateDetail;
  last?: boolean;
}) {
  const tone = gateTone(entry?.result);
  return (
    <View style={[styles.row, !last && styles.rowLine]}>
      <View style={[styles.badge, { backgroundColor: tone.soft }]}>
        <Text variant="captionStrong" color={tone.color}>{GATE_LABEL[gate]}</Text>
      </View>
      <View style={styles.rowText}>
        <View style={styles.rowTitle}>
          <Text variant="bodyStrong">{GATE_LABEL[gate]}闸</Text>
          <Text variant="captionStrong" color={tone.color}>{tone.label}</Text>
        </View>
        <Text variant="caption" color={colors.muted} style={styles.rowDetail}>
          {gateDetailText(gate, entry?.detail ?? {})}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  strip: {
    flexDirection: "row",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    paddingVertical: spacing.base,
  },
  stripDark: { borderColor: colors.whiteOverlay12 },
  cell: { flex: 1, gap: 3, paddingHorizontal: spacing.md },
  cellLine: { borderRightWidth: StyleSheet.hairlineWidth, borderRightColor: colors.line },
  cellDark: { borderRightWidth: StyleSheet.hairlineWidth, borderRightColor: colors.whiteOverlay10 },
  cellHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 4 },
  row: { flexDirection: "row", gap: spacing.base, paddingVertical: spacing.base },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  badge: {
    width: 34,
    height: 34,
    borderRadius: radii.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  rowText: { flex: 1, gap: 3 },
  rowTitle: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  rowDetail: { lineHeight: 17 },
});
