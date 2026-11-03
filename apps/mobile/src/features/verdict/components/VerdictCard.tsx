import { StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import type { GateKey, VerdictSummary } from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";
import {
  formatTime,
  gateLabel,
  pct,
  pickDirectionLabel,
} from "@/lib/format";
import { colors, gradients, radii, shadows, spacing, type } from "@/theme/tokens";
import { Button, StatusDot, Text } from "@/components/ui";
import { GateStrip } from "./Gates";
import { ProbabilityBar } from "./Probability";
import { SealLine } from "./Seal";

interface VerdictCardProps {
  verdict: VerdictSummary;
  betExists?: boolean;
  onOpen: () => void;
  onBet?: () => void;
  onWhyNot?: () => void;
  onSeal?: () => void;
}

function statusMeta(status: string): { label: string; color: string } {
  if (status === "promoted") return { label: "三关全过", color: colors.greenAccent };
  if (status === "killed") return { label: "已砍", color: colors.danger };
  if (status === "screening") return { label: "复核中", color: colors.amber };
  return { label: status, color: colors.muted };
}

function pendingGate(verdict: VerdictSummary): GateKey | null {
  return (["market", "model", "price"] as GateKey[]).find(
    (gate) => verdict.gates[gate] === "pending_data",
  ) ?? null;
}

/**
 * 判决卡是产品的最小信息单元：
 * 结论/概率/抽水/三关/封存必须在一屏内可读，详细情报下沉到详情页。
 */
export function VerdictCard({
  verdict,
  betExists = false,
  onOpen,
  onBet,
  onWhyNot,
  onSeal,
}: VerdictCardProps) {
  const { copy } = usePersonaContent();
  const dark = verdict.status === "promoted";
  const status = statusMeta(verdict.status);
  const pending = pendingGate(verdict);
  const pickLabel = verdict.pick?.dir
    ? pickDirectionLabel(verdict.pool, verdict.pick.dir)
    : "暂不选择";
  const pickProb = verdict.pick?.prob ?? null;
  const summary = copy.verdictSummary({
    status: verdict.status,
    pickLabel,
    prob: pickProb,
    rake: verdict.rake,
    pendingGate: pending ? gateLabel(pending) + "闸" : null,
    gateNote: pending ? "数据没齐，先不推。" : "",
  });

  const body = (
    <>
      <View style={styles.head}>
        <View style={styles.status}>
          <StatusDot color={dark ? colors.greenAccent : status.color} />
          <Text variant="captionStrong" color={dark ? colors.greenAccent : status.color}>
            {status.label}
          </Text>
        </View>
        <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
          {verdict.matchNo} · {formatTime(verdict.kickoff)} 停售
        </Text>
      </View>

      <Text variant="h1" color={dark ? colors.inkInverse : colors.ink} style={styles.match}>
        {verdict.home} <Text variant="h2" color={dark ? colors.mutedInverse : colors.muted}>vs</Text>{" "}
        {verdict.away}
      </Text>
      <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
        {verdict.league || "联赛待同步"} ·{" "}
        {verdict.pool === "hhad" ? `让球 ${verdict.goalLine ?? ""}` : "胜平负"}
      </Text>

      <View style={styles.pickRow}>
        <View style={styles.pickLeft}>
          <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>选择</Text>
          <View style={styles.pickLine}>
            <Text variant="h2" color={dark ? colors.inkInverse : colors.ink}>
              {pickLabel}
            </Text>
            {verdict.pick?.dir && verdict.goalLine ? (
              <View style={[styles.lineChip, dark && styles.lineChipDark]}>
                <Text variant="caption" color={dark ? colors.inkInverse : colors.muted}>
                  让 {verdict.goalLine}
                </Text>
              </View>
            ) : null}
          </View>
        </View>
        <View style={styles.probRight}>
          <Text variant="metric" color={dark ? colors.inkInverse : colors.ink}>
            {pickProb != null ? pct(pickProb) : "—"}
          </Text>
          <Text variant="caption" color={dark ? colors.mutedInverse : colors.muted}>
            {pickProb != null ? "模型置信" : "模型置信待定"}
          </Text>
        </View>
      </View>

      <View style={[styles.rakeRow, dark && styles.rakeRowDark]}>
        <Text variant="small" color={dark ? colors.mutedInverse : colors.muted}>官方定价抽水</Text>
        <View style={styles.rakeValue}>
          <Text variant="bodyStrong" color={dark ? colors.greenAccent : colors.green}>
            {pct(verdict.rake)}
          </Text>
          <Text variant="caption" color={dark ? colors.mutedInverse : colors.subtle}>
            阈值 {pct(verdict.rakeThreshold)}
          </Text>
        </View>
      </View>

      <Text variant="body" color={dark ? colors.inkInverse : colors.ink} style={styles.summary}>
        {summary}
      </Text>

      <ProbabilityBar probs={verdict.probs} dark={dark} />

      <GateStrip
        gates={verdict.gates}
        dark={dark}
        values={{
          price: pct(verdict.rake),
          market: verdict.gates.market === "pass" ? "已收敛" : "待数据",
          model: pickProb != null ? pct(pickProb) : "待定",
        }}
      />

      <View style={styles.actions}>
        {dark ? (
          <>
            <Button
              label={betExists ? copy.bought : copy.buy}
              variant="darkPrimary"
              onPress={onBet}
              disabled={betExists}
              style={styles.action}
            />
            <Button label={copy.detail} variant="darkGhost" onPress={onOpen} style={styles.action} />
          </>
        ) : (
          <>
            <Button label={copy.pendingCta} variant="secondary" onPress={onWhyNot} style={styles.action} />
            <Button label={copy.detail} variant="primary" onPress={onOpen} style={styles.action} />
          </>
        )}
      </View>

      <SealLine hash={verdict.hash} sealed={verdict.sealed} dark={dark} onPress={onSeal} />
    </>
  );

  if (dark) {
    return (
      <LinearGradient
        colors={gradients.verdict}
        start={{ x: 0.1, y: 0 }}
        end={{ x: 0.9, y: 1 }}
        style={styles.darkCard}
      >
        {body}
      </LinearGradient>
    );
  }

  // 卡片本身不做点击：内部有多枚操作按钮，外层 Pressable 会造成点击冒泡/误导航。
  return <View style={[styles.lightCard, pending && styles.pendingCard]}>{body}</View>;
}

const styles = StyleSheet.create({
  darkCard: {
    borderRadius: radii.hero,
    padding: spacing.xl,
    marginTop: spacing.base,
    borderWidth: 1,
    borderColor: colors.heroLine,
    ...shadows.card,
  },
  lightCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.hero,
    padding: spacing.xl,
    marginTop: spacing.base,
    borderWidth: 1,
    borderColor: colors.line,
    ...shadows.card,
  },
  pendingCard: { borderColor: colors.amberLine },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  status: { flexDirection: "row", alignItems: "center", gap: 6 },
  match: { marginTop: spacing.md },
  pickRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.base,
    marginTop: spacing.xl,
  },
  pickLeft: { flex: 1, gap: 3 },
  pickLine: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flexWrap: "wrap" },
  lineChip: {
    borderWidth: 1,
    borderColor: colors.lineStrong,
    borderRadius: 7,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  lineChipDark: { borderColor: "rgba(255,255,255,0.28)" },
  probRight: { alignItems: "flex-end", gap: 1 },
  rakeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    marginTop: spacing.xl,
    paddingTop: spacing.base,
  },
  rakeRowDark: { borderTopColor: "rgba(255,255,255,0.12)" },
  rakeValue: { alignItems: "flex-end", gap: 0 },
  summary: { marginVertical: spacing.base, lineHeight: 22, fontSize: type.body.fontSize },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xl },
  action: { flex: 1 },
});
