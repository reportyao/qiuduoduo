import { StyleSheet, View } from "react-native";
import type {
  SportmonksIntelData,
  SportmonksPredictionHighlight,
  SportmonksStandingRow,
} from "@/domain/types";
import { Card, Chip, Text } from "@/components/ui";
import { ageLabel } from "@/lib/freshness";
import { colors, spacing } from "@/theme/tokens";

function pct(value?: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

function sectionAge(data: SportmonksIntelData, key: string): string {
  return ageLabel(data.sections?.[key]?.capturedAt || data.capturedAt) || "已更新";
}

function formText(form: string[] | undefined): string {
  return form && form.length ? form.join(" ") : "—";
}

function standingLine(label: string, row?: SportmonksStandingRow): string {
  if (!row) return `${label}：积分榜未同步`;
  const record = `${row.played ?? "—"} 场 ${row.won ?? "—"}胜${row.drawn ?? "—"}平${row.lost ?? "—"}负`;
  return `${label}：第 ${row.position ?? "—"} · ${row.points ?? "—"} 分 · ${record} · ${formText(row.form)}`;
}

function predictionValue(item: SportmonksPredictionHighlight): string {
  if (item.key === "CORRECT_SCORE_PROBABILITY" && item.scores?.length) {
    return item.scores
      .slice(0, 3)
      .map((row) => `${row.score} ${pct(row.probability)}`)
      .join(" · ");
  }
  const values = item.values ?? {};
  if (item.key === "BTTS_PROBABILITY") {
    return `是 ${pct(values.yes)} / 否 ${pct(values.no)}`;
  }
  if (item.key === "OVER_UNDER_2_5_PROBABILITY") {
    return `大 ${pct(values.yes)} / 小 ${pct(values.no)}`;
  }
  if (item.key === "DOUBLE_CHANCE_PROBABILITY") {
    return `主或平 ${pct(values.draw_home)} / 平或客 ${pct(values.draw_away)} / 主或客 ${pct(values.home_away)}`;
  }
  if (item.key === "FIRST_HALF_WINNER_PROBABILITY") {
    return `主 ${pct(values.home)} / 平 ${pct(values.draw)} / 客 ${pct(values.away)}`;
  }
  if (item.key === "TEAM_TO_SCORE_FIRST_PROBABILITY") {
    return `主先进 ${pct(values.home)} / 客先进 ${pct(values.away)} / 无进球 ${pct(values.draw)}`;
  }
  return Object.entries(values)
    .filter(([, value]) => value != null)
    .map(([key, value]) => `${key} ${pct(value)}`)
    .join(" / ");
}

function LineupSide({ side }: { side: NonNullable<SportmonksIntelData["lineups"]>["home"] }) {
  if (!side) return null;
  return (
    <View style={styles.lineupSide}>
      <View style={styles.sideHead}>
        <Text variant="captionStrong" numberOfLines={1} style={styles.flex}>{side.teamName || "—"}</Text>
        <Chip label={side.formation || "阵型待定"} tone="neutral" />
      </View>
      {side.starters.slice(0, 11).map((player) => (
        <Text key={`${side.teamId}-${player.name}`} variant="caption" color={colors.muted} numberOfLines={1}>
          {player.number != null ? `${player.number}. ` : ""}{player.name}
        </Text>
      ))}
    </View>
  );
}

export function SportmonksIntelSection({ data }: { data?: SportmonksIntelData | null }) {
  if (!data) return null;
  const homeLine = data.lineups?.home;
  const awayLine = data.lineups?.away;
  const hasLineups = Boolean(homeLine?.starters?.length && awayLine?.starters?.length);
  const standings = data.standings;
  const hasStandings = Boolean(standings?.home || standings?.away);
  const hasConditions = Boolean(
    data.venue || data.weather || data.referees?.main || data.coaches?.home || data.coaches?.away,
  );
  const highlights = data.predictionHighlights ?? [];
  const markets = data.marketBoard ?? [];
  return (
    <>
      {data.postmatch ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <Text variant="h3">赛后复盘</Text>
            <Text variant="caption" color={colors.subtle}>赛后</Text>
          </View>
          <Text variant="h2">
            {data.postmatch.scoreHome ?? "—"} - {data.postmatch.scoreAway ?? "—"}
          </Text>
          <Text variant="small" color={colors.muted}>
            xG {data.postmatch.xgHome ?? "—"} / {data.postmatch.xgAway ?? "—"}
          </Text>
          {data.postmatch.goals.length ? (
            <View style={styles.goals}>
              {data.postmatch.goals.map((goal, index) => (
                <Text key={`${goal.minute}-${goal.player}-${index}`} variant="caption" color={colors.muted}>
                  {goal.minute != null ? `${goal.minute}'` : "—"} {goal.player}
                  {goal.side ? `（${goal.side === "home" ? "主" : "客"}）` : ""}
                  {goal.result ? ` · ${goal.result}` : ""}
                </Text>
              ))}
            </View>
          ) : null}
        </Card>
      ) : null}
      {hasLineups ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <Text variant="h3">首发与阵型</Text>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "lineups")}</Text>
          </View>
          <View style={styles.lineupGrid}>
            <LineupSide side={homeLine} />
            <LineupSide side={awayLine} />
          </View>
          {data.sidelined?.length ? (
            <View style={styles.chips}>
              {data.sidelined.map((row) => (
                <Chip
                  key={`${row.playerName}-${row.side}`}
                  label={`${row.playerName} · ${row.typeLabel}`}
                  tone="amber"
                />
              ))}
            </View>
          ) : (
            <Text variant="caption" color={colors.subtle}>暂无公开伤停名单</Text>
          )}
        </Card>
      ) : null}

      {hasStandings ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <Text variant="h3">积分榜与近况</Text>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "standings")}</Text>
          </View>
          <Text variant="small" color={colors.muted}>{standingLine("主队", standings?.home)}</Text>
          <Text variant="small" color={colors.muted}>{standingLine("客队", standings?.away)}</Text>
          {data.h2h?.length ? (
            <View style={styles.h2h}>
              <Text variant="captionStrong">近期交锋</Text>
              {data.h2h.map((item) => (
                <Text key={`${item.date}-${item.home}-${item.away}`} variant="caption" color={colors.muted}>
                  {item.date} · {item.home} {item.scoreHome}-{item.scoreAway} {item.away}
                </Text>
              ))}
            </View>
          ) : null}
        </Card>
      ) : null}

      {hasConditions ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <Text variant="h3">场地与环境</Text>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "conditions")}</Text>
          </View>
          {data.venue ? (
            <Text variant="small" color={colors.muted}>
              {data.venue.name || "球场待同步"} · {data.venue.city || "城市待同步"}
              {data.venue.capacity ? ` · 容量 ${data.venue.capacity}` : ""}
            </Text>
          ) : null}
          {data.weather ? (
            <Text variant="small" color={colors.muted}>
              天气 {data.weather.description || "—"} · 日间 {data.weather.temperature?.day ?? "—"}°C
              · 风速 {data.weather.wind?.speed ?? "—"}
            </Text>
          ) : null}
          {data.referees?.main ? (
            <Text variant="small" color={colors.muted}>
              主裁 {data.referees.main.name}
              {data.referees.crewCount ? ` · 裁判组 ${data.referees.crewCount} 人` : ""}
            </Text>
          ) : null}
          {data.coaches?.home?.name || data.coaches?.away?.name ? (
            <Text variant="small" color={colors.muted}>
              主教练 {data.coaches?.home?.name || "—"} / {data.coaches?.away?.name || "—"}
            </Text>
          ) : null}
        </Card>
      ) : null}

      {data.expectedLineups || data.prematchNews?.length ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <Text variant="h3">赛前动态</Text>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "news")}</Text>
          </View>
          {data.expectedLineups ? (
            <Text variant="small" color={colors.muted}>
              预计首发已同步 · {data.expectedLineups} 条
            </Text>
          ) : null}
          {(data.prematchNews ?? []).map((item, index) => (
            <View key={`${item.title}-${index}`} style={styles.newsRow}>
              {item.title ? <Text variant="captionStrong">{item.title}</Text> : null}
              {item.text ? <Text variant="caption" color={colors.muted}>{item.text}</Text> : null}
            </View>
          ))}
        </Card>
      ) : null}

      {highlights.length || markets.length ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <Text variant="h3">预测</Text>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "predictions")}</Text>
          </View>
          {highlights.map((item) => (
            <View key={item.key} style={styles.predictionRow}>
              <Text variant="captionStrong" style={styles.predictionLabel}>{item.label}</Text>
              <Text variant="caption" color={colors.muted} style={styles.flex}>{predictionValue(item)}</Text>
            </View>
          ))}
          {markets.map((market) => (
            <View key={market.key} style={styles.marketRow}>
              <Text variant="captionStrong" style={styles.predictionLabel}>
                {market.name}{market.line ? ` ${market.line}` : ""}
              </Text>
              <Text variant="caption" color={colors.muted} style={styles.flex}>
                {market.selections.map((row) => (
                  `${row.label} ${row.price ?? "—"}${row.probability != null ? `（${row.probability.toFixed(1)}%）` : ""}`
                )).join(" · ")}
              </Text>
            </View>
          ))}
        </Card>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.base, gap: spacing.sm },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  lineupGrid: { flexDirection: "row", gap: spacing.base },
  lineupSide: { flex: 1, gap: 2 },
  sideHead: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginBottom: 2 },
  flex: { flex: 1 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  h2h: { gap: 2, marginTop: spacing.xs },
  predictionRow: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  newsRow: { gap: 1, marginTop: 2 },
  goals: { gap: 2, marginTop: spacing.xs },
  marketRow: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start", marginTop: 2 },
  predictionLabel: { width: 70 },
  note: { lineHeight: 17, marginTop: spacing.xs },
});
