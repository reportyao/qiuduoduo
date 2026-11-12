import { memo } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
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
  return form && form.length ? form.join(" ") : "—";
}

function IntelNameCard({ card }: { card: IntelCard }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHead}>
        <Text variant="captionStrong" color={colors.green}>{card.label}</Text>
      </View>
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
        ? `伤停 ${intel.injuries.slice(0, 2).join("、")}`
        : age("lineups") || "首发已同步",
    });
  }
  if (intel.homePosition != null || intel.awayPosition != null) {
    cards.push({
      key: "standings",
      label: "形势",
      value: `${intel.homePosition ?? "—"} / ${intel.awayPosition ?? "—"}`,
      note: `${formText(intel.homeForm)} / ${formText(intel.awayForm)}`,
    });
  }
  if (intel.weather || intel.referee) {
    cards.push({
      key: "conditions",
      label: "环境",
      value: intel.weather || "天气已同步",
      note: intel.referee ? `主裁 ${intel.referee}` : age("conditions") || "场地与裁判",
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
 * 首页对话里的比赛名片：按分片 TTL 展示情报名片。
 * 完整阵容、积分榜、预测维度、市场与赛后内容都留给详情页。
 */
export const MatchConversationCard = memo(function MatchConversationCard({
  option,
  verdict,
  intel,
  onShowPrediction,
  onOpenMatch,
}: {
  option: BriefMatchOption;
  verdict: VerdictSummary | null;
  intel?: MatchIntelSummary;
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
  return (
    <AssistantMessage>
      <View style={styles.headRow}>
        <Text variant="overline" color={colors.green}>这场</Text>
        <Pressable onPress={onOpenMatch} accessibilityRole="button" accessibilityLabel="比赛详情" hitSlop={8}>
          <Text variant="captionStrong" color={colors.green}>比赛详情 ›</Text>
        </Pressable>
      </View>
      <Text variant="h3" style={styles.match}>
        {option.home} <Text variant="small" color={colors.muted}>vs</Text> {option.away}
      </Text>
      <Text variant="caption" color={colors.muted}>
        {option.matchNo} · {option.league || "联赛待同步"} · {formatTime(option.kickoff)} 停售
      </Text>

      {cards.length ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.cardRow}
          style={styles.cardScroll}
        >
          {cards.map((card) => <IntelNameCard key={card.key} card={card} />)}
        </ScrollView>
      ) : (
        <View style={styles.cardRow}>
          {["阵容", "形势", "环境"].map((label) => (
            <View key={label} style={styles.card}>
              <Text variant="captionStrong" color={colors.green}>{label}</Text>
              <Text variant="captionStrong">同步中</Text>
              <Text variant="caption" color={colors.muted}>正在拉取</Text>
            </View>
          ))}
        </View>
      )}

      <View style={styles.prediction}>
        <View style={styles.flex}>
          <Text variant="caption" color={colors.subtle}>预测</Text>
          <Text variant="h3">{direction ?? "预测生成中"}</Text>
        </View>
        <Text variant="metric" color={colors.green}>{probability != null ? pct(probability) : "—"}</Text>
      </View>

      <View style={styles.actions}>
        <Button
          label="看完整预测"
          variant="primary"
          onPress={onShowPrediction}
          disabled={!verdict}
          style={styles.action}
        />
        <Button
          label="比赛详情"
          variant="secondary"
          onPress={onOpenMatch}
          style={styles.action}
        />
      </View>
    </AssistantMessage>
  );
});

const styles = StyleSheet.create({
  headRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  match: { marginTop: spacing.sm },
  cardScroll: { marginTop: spacing.base },
  cardRow: { flexDirection: "row", gap: spacing.xs },
  card: {
    width: 132,
    minHeight: 82,
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    padding: spacing.sm,
    gap: 2,
  },
  cardHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
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
});
