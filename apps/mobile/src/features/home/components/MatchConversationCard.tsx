import { memo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { VerdictSummary } from "@/domain/types";
import { Button, Text } from "@/components/ui";
import { ageLabel } from "@/lib/freshness";
import { formatTime, pct, pickDirectionLabel } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import type { BriefMatchOption } from "./BriefMatchPicker";
import type { MatchIntelSummary } from "../conversation";
import { AssistantMessage } from "./ConversationShell";

interface IntelCard {
  key: string;
  label: string;
  value: string;
  note: string;
}

function formText(form: string[] | undefined): string {
  if (!form?.length) return "—";
  const wins = form.filter((item) => item === "W").length;
  const draws = form.filter((item) => item === "D").length;
  const losses = form.filter((item) => item === "L").length;
  return `${wins}胜${draws}平${losses}负`;
}

function IntelNameCard({ card }: { card: IntelCard }) {
  return (
    <View style={styles.card}>
      <Text variant="captionStrong" color={colors.green}>{card.label}</Text>
      <Text variant="captionStrong" numberOfLines={2}>{card.value}</Text>
      <Text variant="caption" color={colors.muted} numberOfLines={2}>{card.note}</Text>
    </View>
  );
}

function buildCards(intel?: MatchIntelSummary): IntelCard[] {
  if (!intel) return [];
  const cards: IntelCard[] = [];
  const age = (key: string) => ageLabel(intel.sections?.[key] ?? intel.capturedAt);
  const lineup = intel.homeFormation || intel.awayFormation;
  if (lineup) {
    cards.push({
      key: "lineups",
      label: "阵容",
      value: `${intel.homeFormation || "—"} / ${intel.awayFormation || "—"}`,
      note: intel.injuries.length
        ? `伤停 ${intel.injuries.slice(0, 2).join("、")}${age("lineups") ? ` · ${age("lineups")}` : ""}`
        : age("lineups") || "首发已同步",
    });
  }
  if (intel.homePosition != null || intel.awayPosition != null) {
    cards.push({
      key: "standings",
      label: "积分榜",
      value: `第 ${intel.homePosition ?? "—"} / 第 ${intel.awayPosition ?? "—"}`,
      note: `主 ${formText(intel.homeForm)} / 客 ${formText(intel.awayForm)}${age("standings") ? ` · ${age("standings")}` : ""}`,
    });
  }
  if (intel.weather || intel.referee) {
    cards.push({
      key: "conditions",
      label: "环境",
      value: intel.weather || "天气已同步",
      note: intel.referee
        ? `主裁 ${intel.referee}${age("conditions") ? ` · ${age("conditions")}` : ""}`
        : age("conditions") || "场地与裁判",
    });
  }
  if (intel.prediction) {
    cards.push({
      key: "predictions",
      label: "预测",
      value: intel.prediction,
      note: age("predictions") || "多维概率",
    });
  }
  if (intel.market) {
    cards.push({
      key: "markets",
      label: "市场",
      value: intel.market,
      note: age("markets") || "盘口概率",
    });
  }
  if (intel.h2h) {
    cards.push({
      key: "h2h",
      label: "交锋",
      value: intel.h2h,
      note: age("h2h") || "历史对阵",
    });
  }
  if (intel.news) {
    cards.push({
      key: "news",
      label: "动态",
      value: intel.news,
      note: age("news") || "赛前情报",
    });
  }
  return cards;
}

/**
 * 首页对话里的比赛名片：只放摘要和情报名片。
 * 完整阵容、积分榜、25 维预测、市场与赛后内容都留给详情页。
 */
export const MatchConversationCard = memo(function MatchConversationCard({
  option,
  verdict,
  intel,
  predictionShown = false,
  onShowPrediction,
  onOpenMatch,
}: {
  option: BriefMatchOption;
  verdict: VerdictSummary | null;
  intel?: MatchIntelSummary;
  predictionShown?: boolean;
  onShowPrediction: () => void;
  onOpenMatch: () => void;
}) {
  const pick = verdict?.pick;
  const marketKey = verdict
    ? (["home", "draw", "away"] as const).reduce(
        (best, key) => verdict.probs[key] > verdict.probs[best] ? key : best, "home")
    : "home";
  const direction = pick?.dir
    ? pickDirectionLabel(verdict?.pool ?? "had", pick.dir)
    : verdict
      ? pickDirectionLabel(verdict.pool, marketKey === "home" ? "主胜" : marketKey === "draw" ? "平局" : "客胜")
      : null;
  const probability = pick?.prob ?? (verdict ? verdict.probs[marketKey] : null);
  const cards = buildCards(intel);
  const visibleCards = verdict ? cards.slice(0, 4) : cards;
  return (
    <AssistantMessage>
      <Text variant="overline" color={colors.green}>这场</Text>
      <Text variant="h3" style={styles.match}>
        {option.home} <Text variant="small" color={colors.muted}>vs</Text> {option.away}
      </Text>
      <Text variant="caption" color={colors.muted}>
        {option.matchNo} · {option.league || "联赛待同步"} · {formatTime(option.kickoff)} 停售
      </Text>

      <View style={styles.cardGrid}>
        {visibleCards.length ? visibleCards.map((card) => <IntelNameCard key={card.key} card={card} />) : (
          ["阵容", "积分榜", "环境"].map((label) => (
            <View key={label} style={styles.card}>
              <Text variant="captionStrong" color={colors.green}>{label}</Text>
              <Text variant="captionStrong">同步中</Text>
              <Text variant="caption" color={colors.muted}>正在拉取</Text>
            </View>
          ))
        )}
      </View>
      {verdict && cards.length > visibleCards.length ? (
        <Pressable onPress={onOpenMatch} accessibilityRole="button" accessibilityLabel="查看完整情报" hitSlop={6}>
          <Text variant="captionStrong" color={colors.green} style={styles.more}>
            完整 {cards.length} 项情报在详情 ›
          </Text>
        </Pressable>
      ) : null}

      <View style={styles.prediction}>
        <View style={styles.flex}>
          <Text variant="caption" color={colors.subtle}>预测</Text>
          <Text variant="h3">{direction ?? "暂无方向"}</Text>
        </View>
        {probability != null ? (
          <Text variant="metric" color={colors.green}>{pct(probability)}</Text>
        ) : null}
      </View>

      {verdict ? (
        <View style={styles.actions}>
          <Button
            label={predictionShown ? "预测已展开" : "看完整预测"}
            variant="primary"
            onPress={onShowPrediction}
            disabled={predictionShown}
            style={styles.action}
          />
          <Button label="完整详情" variant="secondary" onPress={onOpenMatch} style={styles.action} />
        </View>
      ) : (
        <Pressable onPress={onOpenMatch} accessibilityRole="button" accessibilityLabel="为什么没有预测方向" hitSlop={6}>
          <Text variant="captionStrong" color={colors.muted} style={styles.why}>
            为什么没方向 ›
          </Text>
        </Pressable>
      )}
    </AssistantMessage>
  );
});

const styles = StyleSheet.create({
  match: { marginTop: spacing.sm },
  cardGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.base },
  card: {
    width: "48.5%",
    minHeight: 76,
    backgroundColor: colors.surfaceSunken,
    borderRadius: radii.md,
    padding: spacing.md,
    gap: 2,
  },
  more: { marginTop: spacing.xs },
  prediction: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginTop: spacing.base,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  flex: { flex: 1 },
  actions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.base },
  action: { flex: 1 },
  why: { marginTop: spacing.base },
});
