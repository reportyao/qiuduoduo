import { StyleSheet, View } from "react-native";
import { useBetPostmortemQuery } from "@/features/records/queries";
import { errorText } from "@/lib/errors";
import { decimalToFormat, money, oddsFormatLabel, pct, pickDirectionLabel } from "@/lib/format";
import { useOddsFormat } from "@/features/preferences/prefsStore";
import { colors, spacing } from "@/theme/tokens";
import { Card, ErrorState, KeyValueRow, Sheet, Skeleton, Text } from "@/components/ui";

export function PostmortemSheet({
  betId,
  onClose,
}: {
  betId: number | null;
  onClose: () => void;
}) {
  const query = useBetPostmortemQuery(betId ?? undefined);
  const pm = query.data;
  const oddsFormat = useOddsFormat();

  return (
    <Sheet
      visible={Boolean(betId)}
      onClose={onClose}
      title="这一注复盘"
      subtitle="输赢都归因，不重写历史。"
    >
      {query.isLoading ? (
        <View style={{ gap: spacing.sm }}>
          <Skeleton height={100} radius={14} />
          <Skeleton height={120} radius={14} />
        </View>
      ) : query.isError ? (
        <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
      ) : pm ? (
        <>
          <Card tone={pm.settled === "win" ? "positive" : pm.settled === "lose" ? "negative" : "default"} style={styles.hero}>
            <Text variant="caption" color={colors.muted}>{pm.matchNo} · {pm.tradeDate}</Text>
            <Text variant="h3">{pm.match}</Text>
            <Text variant="small" color={colors.muted}>
              {pm.pick?.dir
                ? `${pickDirectionLabel(pm.pool, pm.pick.dir)} @${
                  pm.bet?.sp != null
                    ? `${decimalToFormat(pm.bet.sp, oddsFormat)}（${oddsFormatLabel(oddsFormat)}）`
                    : pm.pick.sp != null
                      ? decimalToFormat(pm.pick.sp, oddsFormat)
                      : "--"
                }`
                : "暂无预测"}
              {pm.settled ? ` · ${pm.settled === "win" ? "已中" : "未中"} ${pm.resultScore ?? ""}` : " · 待结算"}
            </Text>
            {pm.bet ? (
              <View style={styles.betRow}>
                <Text variant="caption" color={colors.muted}>注额 {money(pm.bet.amount)}</Text>
                <Text
                  variant="bodyStrong"
                  color={pm.bet.pnl == null ? colors.muted : pm.bet.pnl >= 0 ? colors.brand : colors.loss}
                >
                  {pm.bet.pnl != null ? money(pm.bet.pnl) : "待结算"}
                </Text>
              </View>
            ) : null}
          </Card>

          {pm.attribution ? (
            <View style={styles.block}>
              <Text variant="overline" color={colors.brand}>归因</Text>
              <Text variant="bodyStrong">{pm.attribution.class ?? "未归因"}</Text>
              <Text variant="small" color={colors.muted} style={styles.text}>{pm.attribution.note}</Text>
            </View>
          ) : null}

          <View style={styles.kvBlock}>
            <KeyValueRow label="玩法" value={pm.pool === "hhad" ? `让球 ${pm.goalLine ?? ""}` : "胜平负"} />
            <KeyValueRow label="预测概率" value={pm.pick?.prob != null ? pct(pm.pick.prob) : "未提供"} />
            <KeyValueRow label="复盘类型" value={kindLabel(pm.kind)} last />
          </View>

          <Card style={styles.whatif}>
            <Text variant="captionStrong" color={colors.amber}>What if</Text>
            <Text variant="small" color={colors.muted} style={styles.text}>{pm.whatIf}</Text>
          </Card>
        </>
      ) : null}
    </Sheet>
  );
}

function kindLabel(kind: string): string {
  if (kind === "promoted") return "通过三关";
  if (kind === "killed") return "未给预测";
  if (kind === "screening") return "复核中";
  return kind;
}

const styles = StyleSheet.create({
  hero: { gap: spacing.xs, marginBottom: spacing.base },
  betRow: { flexDirection: "row", justifyContent: "space-between", marginTop: spacing.xs },
  block: { gap: spacing.xs, marginBottom: spacing.base },
  text: { lineHeight: 20 },
  kvBlock: { backgroundColor: colors.bgElevated, borderRadius: 14, paddingHorizontal: spacing.base },
  whatif: { marginTop: spacing.base, gap: spacing.xs },
});
