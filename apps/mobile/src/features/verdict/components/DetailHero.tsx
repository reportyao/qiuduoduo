import { StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import type { GateKey, VerdictDetail } from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";
import { formatDate, formatTime, gateLabel, pct, pickDirectionLabel, pp } from "@/lib/format";
import { colors, gradients, radii, shadows, spacing } from "@/theme/tokens";
import { Chip, StatusDot, Text } from "@/components/ui";
import { GateStrip } from "./Gates";
import { ProbabilityBar } from "./Probability";
import { SealLine } from "./Seal";

export function DetailHero({
  detail,
  onSeal,
}: {
  detail: VerdictDetail;
  onSeal: () => void;
}) {
  const { copy } = usePersonaContent();
  const dark = detail.status === "promoted";
  const pending = (["market", "model", "price"] as GateKey[]).find(
    (gate) => detail.gates[gate] === "pending_data",
  );
  const pickLabel = detail.pick?.dir
    ? pickDirectionLabel(detail.pool, detail.pick.dir)
    : "暂不选择";
  const summary = copy.verdictSummary({
    status: detail.status,
    pickLabel,
    prob: detail.pick?.prob ?? null,
    rake: detail.rake,
    pendingGate: pending ? `${gateLabel(pending)}闸` : null,
    gateNote: pending ? "数据没齐，先不推。" : "",
  });
  const statusLabel =
    detail.status === "promoted" ? "三关全过" : detail.status === "killed" ? "已砍" : "复核中";
  const statusColor =
    detail.status === "promoted"
      ? colors.greenAccent
      : detail.status === "killed"
        ? colors.danger
        : colors.amber;

  const content = (
    <>
      <View style={styles.head}>
        <View style={styles.status}>
          <StatusDot color={statusColor} />
          <Text variant="captionStrong" color={statusColor}>{statusLabel}</Text>
        </View>
        <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
          {detail.matchNo} · {formatDate(detail.kickoff)} {formatTime(detail.kickoff)} 停售
        </Text>
      </View>

      <Text variant="h1" color={dark ? colors.inkInverse : colors.ink} style={styles.match}>
        {detail.home} <Text variant="h2" color={dark ? colors.mutedInverse : colors.muted}>vs</Text> {detail.away}
      </Text>
      <View style={styles.metaRow}>
        <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
          {detail.league || "联赛待同步"} · {detail.pool === "hhad" ? `让球 ${detail.goalLine ?? ""}` : "胜平负"}
        </Text>
        <Chip label="三关 v3" tone={dark ? "dark" : "neutral"} />
      </View>

      <View style={styles.pickRow}>
        <View style={styles.flex}>
          <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>选择</Text>
          <Text variant="h1" color={dark ? colors.inkInverse : colors.ink}>{pickLabel}</Text>
          <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
            官方抽水 {pct(detail.rake)} · 阈值 {pct(detail.rakeThreshold)}
          </Text>
        </View>
        <View style={styles.prob}>
          <Text variant="metric" color={dark ? colors.inkInverse : colors.ink}>
            {detail.pick?.prob != null ? pct(detail.pick.prob) : "—"}
          </Text>
          <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
            {detail.pick?.prob != null ? "模型置信" : "模型置信待定"}
          </Text>
        </View>
      </View>

      <Text variant="body" color={dark ? colors.inkInverse : colors.ink} style={styles.summary}>
        {summary}
      </Text>
      <ProbabilityBar probs={detail.probs} dark={dark} pool={detail.pool} />
      <GateStrip
        gates={detail.gates}
        dark={dark}
        values={{
          price: pct(detail.rake),
          market:
            typeof detail.gatesDetail.market?.detail.divergence === "number"
              ? pp(detail.gatesDetail.market.detail.divergence as number)
              : detail.gates.market === "pass" ? "已收敛" : "待数据",
          model:
            typeof detail.gatesDetail.model?.detail.top === "number"
              ? pct(detail.gatesDetail.model.detail.top as number)
              : detail.pick?.prob != null ? pct(detail.pick.prob) : "待定",
        }}
      />
      <SealLine hash={detail.payloadHash} sealed={Boolean(detail.sealedAt)} dark={dark} onPress={onSeal} />
      <Text variant="caption" color={dark ? colors.mutedInverse : colors.subtle} style={styles.cutoff}>
        数据截止 {detail.dataCutoff || "待同步"} · 封存于 {detail.sealedAt ? formatDate(detail.sealedAt) : "未封存"}
      </Text>
    </>
  );

  if (dark) {
    return (
      <LinearGradient
        colors={gradients.verdict}
        start={{ x: 0.1, y: 0 }}
        end={{ x: 0.9, y: 1 }}
        style={styles.dark}
      >
        {content}
      </LinearGradient>
    );
  }
  return <View style={[styles.light, pending && styles.pending]}>{content}</View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  dark: {
    borderRadius: radii.hero,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.heroLine,
    ...shadows.card,
  },
  light: {
    backgroundColor: colors.surface,
    borderRadius: radii.hero,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.line,
    ...shadows.card,
  },
  pending: { borderColor: colors.amberLine },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  status: { flexDirection: "row", alignItems: "center", gap: 6 },
  match: { marginTop: spacing.md },
  metaRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 2, flexWrap: "wrap" },
  pickRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.base,
    marginTop: spacing.xl,
  },
  prob: { alignItems: "flex-end" },
  summary: { marginVertical: spacing.base, lineHeight: 22 },
  cutoff: { marginTop: spacing.sm, lineHeight: 16 },
});
