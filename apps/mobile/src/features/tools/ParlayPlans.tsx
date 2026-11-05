import { useState } from "react";
import { StyleSheet, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Button, Card, Chip, Text, useToast } from "@/components/ui";
import { ParlayReport } from "./ParlayReport";
import type { ParlayPlan, ParlayPlanItem } from "./queries";
import type { OddsFormat } from "@/features/preferences/prefsStore";
import { decimalToFormat, money, pct } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

type ReviewedPlanItem = ParlayPlanItem & {
  conditions?: string[];
  invalidators?: string[];
  review?: { status: string } | null;
};

function PlanCard({ item, oddsFormat }: { item: ReviewedPlanItem; oddsFormat: OddsFormat }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const copy = async () => {
    const text = item.check.legs
      .map((leg) => `${leg.match_no} ${leg.home} ${leg.dir_label} @${decimalToFormat(leg.odds, oddsFormat)}`)
      .join(" + ");
    await Clipboard.setStringAsync(`${item.label}：${text}`);
    toast.show("组合已复制", "success");
  };
  return (
    <Card style={styles.card}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="bodyStrong">{item.label} · {item.legs.length} 串 1</Text>
          <Text variant="caption" color={colors.muted}>
            组合赔率 {decimalToFormat(item.check.combo.odds, oddsFormat)} · 成本 {money(item.check.combo.cost, 2)}
          </Text>
        </View>
        <View style={styles.badges}>
          <Chip label={item.check.combo.model_coverage === `${item.legs.length}/${item.legs.length}` ? "模型覆盖" : "模型不完整"}
                tone={item.check.combo.model_coverage === `${item.legs.length}/${item.legs.length}` ? "green" : "amber"} />
          <Chip label={`结构${item.check.scores.structure === "low" ? "低" : item.check.scores.structure === "medium" ? "中" : "高"}`}
                tone={item.check.scores.structure === "low" ? "green" : item.check.scores.structure === "medium" ? "amber" : "danger"} />
        </View>
      </View>
      {item.check.legs.map((leg) => (
        <Text key={leg.verdict_id} variant="small" color={colors.ink}>
          {leg.match_no} {leg.home} vs {leg.away} · {leg.dir_label} @{decimalToFormat(leg.odds, oddsFormat)}
          {leg.model_prob != null ? ` · 模型 ${pct(leg.model_prob)}` : " · 模型未覆盖"}
        </Text>
      ))}
      <Text variant="caption" color={colors.muted}>{item.check.summary}</Text>
      {item.note ? <Text variant="caption" color={colors.amber}>{item.note}</Text> : null}
      {item.conditions?.length ? (
        <Text variant="caption" color={colors.muted}>成立：{item.conditions.slice(0, 2).join("；")}</Text>
      ) : null}
      {item.invalidators?.length ? (
        <Text variant="caption" color={colors.subtle}>失效：{item.invalidators.slice(0, 2).join("；")}</Text>
      ) : null}
      {item.check.risks[0] ? (
        <Text variant="caption" color={colors.amber}>{item.check.risks[0].message}</Text>
      ) : null}
      <View style={styles.actions}>
        <Button label="复制组合" size="sm" variant="secondary" onPress={copy} />
        <Button label={open ? "收起体检" : "看体检"} size="sm" variant="ghost" onPress={() => setOpen((v) => !v)} />
      </View>
      {open ? <ParlayReport data={item.check} oddsFormat={oddsFormat} /> : null}
    </Card>
  );
}

export function ParlayPlans({ data, oddsFormat, reviewed = false }: { data: ParlayPlan; oddsFormat: OddsFormat; reviewed?: boolean }) {
  if (!data.plans.length) {
    return <Text variant="small" color={colors.amber}>{data.message || "今日暂不配组合。"}</Text>;
  }
  return (
    <View style={styles.wrap}>
      <Text variant="caption" color={reviewed ? colors.green : colors.amber}>
        {reviewed ? "参考组合 · AI 复核通过" : "参考·未复核：仅作结构参考，未接入 AI 复核"}
      </Text>
      {data.plans.map((item) => (
        <PlanCard key={item.risk_profile} item={item} oddsFormat={oddsFormat} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, marginTop: spacing.sm },
  card: { gap: spacing.xs },
  head: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  flex: { flex: 1 },
  badges: { alignItems: "flex-end", gap: spacing.xxs },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs },
});
