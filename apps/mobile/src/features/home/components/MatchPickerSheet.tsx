import { useMemo, useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import type { OnSaleItem, VerdictSummary } from "@/domain/types";
import { saleCountdownText, formatTime, tradeDateCnFromKickoff } from "@/lib/format";
import { colors, radii, spacing } from "@/theme/tokens";
import { Chip, Icon, Sheet, StatusDot, Text } from "@/components/ui";

type Filter = "all" | "promoted" | "screening" | "onsale" | "covered";

interface Row {
  matchId: string;
  matchNo: string;
  home: string;
  away: string;
  kickoff: string;
  close: string;
  verdictId: string | null;
  status: string;
  tier?: string | null;
  gates: VerdictSummary["gates"] | null;
  tradeDate: string;
  coverage: OnSaleItem["coverage"];
}

interface MatchPickerSheetProps {
  visible: boolean;
  onClose: () => void;
  verdicts: VerdictSummary[];
  streamDate: string;
  onsale: OnSaleItem[];
  onSelectVerdict: (id: string) => void;
  onSelectMatch: (matchId: string, date: string) => void;
  loading?: boolean;
}

export function MatchPickerSheet({
  visible,
  onClose,
  verdicts,
  streamDate,
  onsale,
  onSelectVerdict,
  onSelectMatch,
  loading = false,
}: MatchPickerSheetProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const byMatch = new Map<string, Row>();
    for (const verdict of verdicts) {
      byMatch.set(verdict.matchId, {
        matchId: verdict.matchId,
        matchNo: verdict.matchNo,
        home: verdict.home,
        away: verdict.away,
        kickoff: verdict.kickoff,
        close: verdict.kickoff,
        verdictId: verdict.id,
        status: verdict.status,
        tier: verdict.tier ?? null,
        gates: verdict.gates,
        tradeDate: streamDate,
        coverage: null,
      });
    }
    for (const match of onsale) {
      if (byMatch.has(match.matchId)) continue;
      byMatch.set(match.matchId, {
        matchId: match.matchId,
        matchNo: match.matchNo,
        home: match.home,
        away: match.away,
        kickoff: match.kickoff,
        close: match.saleClose,
        verdictId: match.verdictId,
        status: match.status ?? "onsale",
        tier: match.tier ?? null,
        gates: match.gates,
        tradeDate: tradeDateCnFromKickoff(match.kickoff),
        coverage: match.coverage,
      });
    }
    const list = Array.from(byMatch.values());
    const filtered = list.filter((row) => {
      if (filter === "promoted" && row.status !== "promoted") return false;
      if (filter === "screening" && row.status !== "screening") return false;
      if (filter === "onsale" && row.verdictId !== null) return false;
      if (filter === "covered" && (row.coverage?.score ?? 0) < 70) return false;
      if (query.trim()) {
        const hay = `${row.home}${row.away}${row.matchNo}`.toLowerCase();
        if (!hay.includes(query.trim().toLowerCase())) return false;
      }
      return true;
    });
    return filtered.sort((a, b) => {
      if (a.status === "promoted" && b.status !== "promoted") return -1;
      if (b.status === "promoted" && a.status !== "promoted") return 1;
      const coverage = (b.coverage?.score ?? 0) - (a.coverage?.score ?? 0);
      return coverage !== 0 ? coverage : a.close.localeCompare(b.close);
    });
  }, [filter, onsale, query, streamDate, verdicts]);

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      title="选一场比赛"
      subtitle="点一场，先看账再决定。没把握的场次会明确标出。"
    >
      <View style={styles.search}>
        <Icon name="search-outline" size={17} color={colors.subtle} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="搜球队或场次"
          placeholderTextColor={colors.subtle}
          style={styles.input}
          selectionColor={colors.green}
          accessibilityLabel="搜索比赛"
        />
      </View>

      <View style={styles.filters}>
        <Chip label="全部" selected={filter === "all"} onPress={() => setFilter("all")} />
        <Chip label="通过三关" selected={filter === "promoted"} onPress={() => setFilter("promoted")} />
        <Chip label="复核中" selected={filter === "screening"} onPress={() => setFilter("screening")} />
        <Chip label="仅在售" selected={filter === "onsale"} onPress={() => setFilter("onsale")} />
        <Chip label="覆盖足" selected={filter === "covered"} onPress={() => setFilter("covered")} />
      </View>

      <View style={styles.list}>
        {rows.length === 0 ? (
          <View style={styles.empty}>
            <Text variant="small" color={colors.muted}>
              {loading ? "正在同步今日比赛…" : "没有符合条件的比赛。"}
            </Text>
          </View>
        ) : (
          rows.map((row, index) => (
            <Pressable
              key={row.matchId}
              onPress={() => {
                onClose();
                if (row.verdictId) onSelectVerdict(row.verdictId);
                else onSelectMatch(row.matchId, row.tradeDate);
              }}
              accessibilityRole="button"
              accessibilityLabel={`${row.home} 对 ${row.away}`}
              style={({ pressed }) => [
                styles.row,
                index < rows.length - 1 && styles.rowLine,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.timeCol}>
                <Text variant="captionStrong">{formatTime(row.kickoff)}</Text>
                <Text variant="caption" color={colors.subtle}>{row.matchNo}</Text>
              </View>
              <View style={styles.teams}>
                <Text variant="bodyStrong" numberOfLines={1}>
                  {row.home} <Text variant="caption" color={colors.muted}>vs</Text> {row.away}
                </Text>
                <Text variant="caption" color={colors.muted}>
                  {row.verdictId ? rowStatus(row.status, row.tier) : `在售 · ${saleCountdownText(row.close)}`}
                  {row.coverage ? ` · 覆盖 ${row.coverage.score}` : ""}
                </Text>
              </View>
              {row.gates?.price === "pass" ? (
                <StatusDot color={row.status === "promoted" ? colors.green : colors.amber} />
              ) : (
                <Icon name="chevron-forward" size={15} color={colors.subtle} />
              )}
            </Pressable>
          ))
        )}
      </View>
    </Sheet>
  );
}

function rowStatus(status: string, tier?: string | null): string {
  if (tier === "verified") return "预测 · 看完整依据";
  if (tier === "market_reference") return "预测 · 看完整依据";
  if (tier === "avoid") return "赛前 · 看情报";
  if (tier === "no_data") return "赛前";
  if (status === "promoted") return "预测 · 看完整依据";
  if (status === "screening") return "预测";
  if (status === "killed") return "赛前 · 看情报";
  return "预测";
}

const styles = StyleSheet.create({
  search: {
    height: 46,
    borderRadius: radii.md,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.base,
    gap: spacing.sm,
  },
  input: { flex: 1, color: colors.ink, fontSize: 14 },
  filters: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.base },
  list: { marginTop: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    paddingVertical: spacing.base,
    minHeight: 58,
  },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { opacity: 0.65 },
  timeCol: { width: 54, gap: 1 },
  teams: { flex: 1, gap: 2 },
  empty: { paddingVertical: spacing.x4, alignItems: "center" },
});
