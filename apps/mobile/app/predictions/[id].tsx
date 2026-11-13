import { StyleSheet, View } from "react-native";
import { ScrollView } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, Chip, EmptyState, ErrorState, ProbabilityBreakdown, Skeleton, Text } from "@/components/ui";
import { errorText } from "@/lib/errors";
import { formatDateTime, pct, utcIso } from "@/lib/format";
import { goBackOr } from "@/lib/navigation";
import { colors, layout, radii, spacing } from "@/theme/tokens";
import {
  usePredictionDetailQuery,
  type PredictionAccuracy,
  type PredictionItem,
} from "@/features/matches/queries";
import {
  resultLabel,
  resultTone,
  scoreStatusLabel,
  splitPredictionItems,
} from "@/features/matches/labels";

export default function PredictionHistoryDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const query = usePredictionDetailQuery(id);

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="预测战绩"
        subtitle={query.data ? `${query.data.league || "单场"} · ${query.data.match_no}` : "逐维对照"}
        onBack={() => goBackOr(router)}
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {query.isLoading ? (
          <>
            <Skeleton height={170} radius={22} />
            <Skeleton height={110} radius={18} style={{ marginTop: spacing.base }} />
            <Skeleton height={260} radius={18} style={{ marginTop: spacing.base }} />
          </>
        ) : query.isError || !query.data ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : (
          <Body data={query.data} />
        )}
      </ScrollView>
    </AppScreen>
  );
}

function Body({
  data,
}: {
  data: NonNullable<ReturnType<typeof usePredictionDetailQuery>["data"]>;
}) {
  const { counted, reference } = splitPredictionItems(data.items);
  const score = data.score_home == null || data.score_away == null
    ? "待赛果"
    : `${data.score_home} - ${data.score_away}`;
  return (
    <>
      <Card style={styles.hero}>
        <Text variant="overline" color={colors.green}>赛后复盘</Text>
        <View style={styles.heroTop}>
          <Text variant="caption" color={colors.muted}>
            {formatDateTime(data.kickoff)} 开赛
          </Text>
          <Chip label={scoreStatusLabel(data.status) || "待赛果"} tone={data.status ? "green" : "neutral"} />
        </View>
        <View style={styles.teams}>
          <View style={styles.flex}>
            <Text variant="h3" numberOfLines={1}>{data.home}</Text>
            <Text variant="h3" numberOfLines={1}>{data.away}</Text>
          </View>
          <Text variant="display" style={styles.score}>{score}</Text>
        </View>
        <Text variant="caption" color={colors.muted}>
          {snapshotText(data.snapshot)}
        </Text>
      </Card>

      <Card style={styles.summary}>
        <View style={styles.flex}>
          <Text variant="caption" color={colors.muted}>主流玩法命中率</Text>
          <Text variant="metric" color={colors.green}>{pct(data.summary.hit_rate, 1)}</Text>
        </View>
        <SummaryCount summary={data.summary} />
      </Card>

      <SectionTitle title="计入命中率" count={counted.length} note="按预测条目统计" />
      {counted.length === 0 ? (
        <Text variant="small" color={colors.muted} style={styles.emptyLine}>
          这场没有可计入命中率的主流派生预测。
        </Text>
      ) : (
        <Card padded={false}>{counted.map((item, index) => (
          <ItemRow key={item.type} item={item} last={index === counted.length - 1} />
        ))}</Card>
      )}

      <SectionTitle title="其他维度对照" count={reference.length} note="展示不计入命中率" />
      {reference.length === 0 ? (
        <EmptyState
          icon="layers-outline"
          title="没有其他维度"
          body="这场只有主流玩法预测，没有角球、半全场等对照项。"
        />
      ) : (
        <Card padded={false}>{reference.map((item, index) => (
          <ItemRow key={item.type} item={item} last={index === reference.length - 1} muted />
        ))}</Card>
      )}
    </>
  );
}

function snapshotText(snapshot: {
  status: string;
  captured_at?: string | null;
  locked_at?: string | null;
  source: string;
}): string {
  if (snapshot.status === "missing") {
    return "没有赛前快照；这场不做历史对照，也不补造。";
  }
  const cutoff = snapshot.captured_at
    ? formatDateTime(utcIso(snapshot.captured_at))
    : "时间待同步";
  if (snapshot.status === "locked") {
    return `数据截止 ${cutoff} · 赛前已锁定`;
  }
  return `数据截止 ${cutoff} · 开球后锁定`;
}

function SummaryCount({ summary }: { summary: PredictionAccuracy }) {
  return (
    <View style={styles.summaryCounts}>
      <Count label="命中" value={summary.hit_items} tone={colors.green} />
      <Count label="走水" value={summary.push_items} tone={colors.amber} />
      <Count label="未中" value={summary.miss_items} tone={colors.danger} />
    </View>
  );
}

function Count({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <View style={styles.count}>
      <Text variant="bodyStrong" color={tone}>{value}</Text>
      <Text variant="caption" color={colors.muted}>{label}</Text>
    </View>
  );
}

function SectionTitle({
  title,
  count,
  note,
}: {
  title: string;
  count: number;
  note: string;
}) {
  return (
    <View style={styles.sectionHead}>
      <Text variant="h3">{title}</Text>
      <Text variant="caption" color={colors.muted}>{note} · {count} 项</Text>
    </View>
  );
}

function ItemRow({
  item,
  last,
  muted = false,
}: {
  item: PredictionItem;
  last: boolean;
  muted?: boolean;
}) {
  return (
    <View style={[styles.item, !last && styles.itemLine]}>
      <View style={styles.itemHead}>
        <Text variant={muted ? "small" : "smallStrong"} style={styles.flex} numberOfLines={2}>
          {item.label || item.type}
        </Text>
        <Chip label={resultLabel(item.result)} tone={resultTone(item.result)} />
      </View>
      <Text variant="caption" color={colors.muted}>
        预测 {item.predicted_label || item.predicted_key || "—"}
        {item.predicted_probability != null ? ` · ${pct(item.predicted_probability, 1)}` : ""}
        {item.market_line ? ` · 盘口 ${item.market_line}` : ""}
        {"  ·  "}实际 {item.actual_label || "—"}
      </Text>
      {item.probabilities?.length ? (
        <ProbabilityBreakdown
          items={item.probabilities.map((row) => ({
            key: row.key,
            label: row.label || row.key,
            value: row.probability,
          }))}
          unit="ratio"
          predictedKey={item.predicted_key}
          actualKey={item.actual_key}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.md,
    paddingBottom: 40 + layout.tabBarHeight,
    gap: spacing.sm,
  },
  flex: { flex: 1 },
  hero: {
    borderRadius: radii.hero,
    gap: spacing.md,
    backgroundColor: colors.surface,
  },
  heroTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  teams: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  score: { fontVariant: ["tabular-nums"] },
  summary: { flexDirection: "row", alignItems: "center", gap: spacing.lg },
  summaryCounts: { flexDirection: "row", gap: spacing.lg },
  count: { alignItems: "flex-end", gap: 1 },
  sectionHead: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    marginTop: spacing.base,
  },
  emptyLine: { paddingVertical: spacing.md },
  item: {
    gap: spacing.xs,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  itemHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  itemLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },

});
