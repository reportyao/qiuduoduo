import { StyleSheet, useWindowDimensions, View } from "react-native";
import type {
  SportmonksIntelData,
  SportmonksStandingRow,
} from "@/domain/types";
import { Card, Chip, Text } from "@/components/ui";
import { ageLabel } from "@/lib/freshness";
import { colors, radii, spacing } from "@/theme/tokens";
import { PredictionGroupBoard } from "./PredictionGroupBoard";

function sectionAge(data: SportmonksIntelData, key: string): string {
  return ageLabel(data.sections?.[key]?.capturedAt || data.capturedAt) || "已更新";
}

function formText(form: string[] | undefined): string {
  if (!form?.length) return "—";
  const labels: Record<string, string> = { W: "胜", D: "平", L: "负" };
  return form.map((item) => labels[item] ?? item).join(" ");
}

function standingLine(label: string, row?: SportmonksStandingRow): string {
  if (!row) return `${label}：积分榜未同步`;
  const record = `${row.played ?? "—"} 场 ${row.won ?? "—"}胜${row.drawn ?? "—"}平${row.lost ?? "—"}负`;
  return `${label}：第 ${row.position ?? "—"} · ${row.points ?? "—"} 分 · ${record} · ${formText(row.form)}`;
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
  const { width } = useWindowDimensions();
  const marketWidth = width >= 360 ? "48%" : "100%";
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

      {highlights.length ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <View style={styles.headText}>
              <Text variant="h3">25 维预测</Text>
              <Text variant="caption" color={colors.muted}>
                Sportmonks 概率 · 全部展开
              </Text>
            </View>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "predictions")}</Text>
          </View>
          <PredictionGroupBoard highlights={highlights} />
        </Card>
      ) : null}

      {markets.length ? (
        <Card style={styles.card}>
          <View style={styles.head}>
            <View style={styles.headText}>
              <Text variant="h3">市场参考</Text>
              <Text variant="caption" color={colors.muted}>
                Pinnacle · {markets.length} 个市场
              </Text>
            </View>
            <Text variant="caption" color={colors.subtle}>{sectionAge(data, "predictions")}</Text>
          </View>
          <View style={styles.marketGrid}>
            {markets.map((market) => (
              <View key={market.key} style={[styles.marketCard, { width: marketWidth }]}>
                <View style={styles.marketHead}>
                  <Text variant="captionStrong" style={styles.flex} numberOfLines={1}>
                    {market.name}
                  </Text>
                  {market.line ? (
                    <Text variant="caption" color={colors.green} mono>{market.line}</Text>
                  ) : null}
                </View>
                {market.selections.map((row) => (
                  <View key={`${market.key}-${row.label}`} style={styles.selectionRow}>
                    <Text variant="caption" color={colors.muted} style={styles.flex} numberOfLines={1}>
                      {row.label}
                    </Text>
                    <Text variant="captionStrong" mono>
                      {row.price?.toFixed(2) ?? "—"}
                    </Text>
                    <Text variant="caption" color={colors.subtle} style={styles.probability}>
                      {row.probability != null ? `${row.probability.toFixed(0)}%` : "—"}
                    </Text>
                  </View>
                ))}
              </View>
            ))}
          </View>
        </Card>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: spacing.md, gap: spacing.lg },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.sm },
  headText: { gap: 2, flex: 1 },
  dim: { paddingVertical: spacing.md, gap: 2 },
  dimLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  dimHead: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm },
  marketGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  marketCard: {
    gap: 4,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  marketHead: { flexDirection: "row", alignItems: "baseline", gap: spacing.xs, marginBottom: 2 },
  selectionRow: { flexDirection: "row", alignItems: "baseline", gap: spacing.xs },
  probability: { width: 38, textAlign: "right" },
  lineupGrid: { flexDirection: "row", gap: spacing.xl },
  lineupSide: { flex: 1, gap: 3 },
  sideHead: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginBottom: 2 },
  flex: { flex: 1 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  h2h: { gap: 2, marginTop: spacing.xs },
  newsRow: { gap: 1, marginTop: 2 },
  goals: { gap: 2, marginTop: spacing.xs },
  note: { lineHeight: 17, marginTop: spacing.xs },
});
