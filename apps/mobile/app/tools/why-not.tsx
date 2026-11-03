import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, Chip, EmptyState, ErrorState, Skeleton, Text } from "@/components/ui";
import { useStreamQuery } from "@/features/home/queries";
import { usePersonaContent } from "@/features/personas/usePersona";
import type { GateKey } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { pct, todayCn } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";
import { gateTone } from "@/features/verdict/components/Gates";

interface Row {
  matchId: string;
  matchNo: string;
  home: string;
  away: string;
  status: "killed" | "screening";
  gate: GateKey | null;
  text: string;
}

export default function WhyNotListScreen() {
  const router = useRouter();
  const { copy } = usePersonaContent();
  const query = useStreamQuery(todayCn());
  const stream = query.data?.pages[0];

  const rows = useMemo<Row[]>(() => {
    if (!stream) return [];
    const killed: Row[] = stream.avoid.map((item) => ({
      matchId: item.matchId,
      matchNo: item.matchNo,
      home: item.home,
      away: item.away,
      status: "killed",
      gate: item.gate === "price" || item.gate === "market" || item.gate === "model" ? item.gate : null,
      text: item.why,
    }));
    const pending: Row[] = stream.watch
      .filter((v) => v.status === "screening" && (v.gates.market === "pending_data" || v.gates.model === "pending_data"))
      .map((v) => {
        const gate: GateKey | null = v.gates.market === "pending_data" ? "market" : v.gates.model === "pending_data" ? "model" : null;
        return {
          matchId: v.matchId,
          matchNo: v.matchNo,
          home: v.home,
          away: v.away,
          status: "screening",
          gate,
          text: `价闸已过（抽水 ${pct(v.rake)}），等${gate === "market" ? "国际盘" : "模型"}数据`,
        };
      });
    return [...killed, ...pending].filter((row) => Boolean(row.matchId));
  }, [stream]);

  return (
    <AppScreen bottom={false}>
      <AppHeader title="为什么不推" showAssistant={false} onBack={() => router.back()} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Text variant="overline" color={colors.green}>死因 · 全公开</Text>
        <Text variant="display" style={styles.title}>不推，也是结论。</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          被砍的、还在等数据的，都在这里。点开看它死在哪一关，以及什么条件会让它重新进池。
        </Text>

        {query.isLoading ? (
          <Skeleton height={220} radius={20} style={{ marginTop: spacing.base }} />
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon="checkmark-circle-outline"
            title="今天没有需要解释的场次"
            body="没有已砍或复核中的记录。要么都过了，要么今天还没同步。"
            actionLabel="看今日在售"
            onAction={() => router.push("/tools/on-sale")}
          />
        ) : (
          <View style={styles.list}>
            {rows.map((row) => {
              const tone = gateTone(row.status === "killed" ? "fail" : "pending_data");
              return (
                <Pressable
                  key={`${row.status}-${row.matchId}-${row.matchNo}`}
                  onPress={() => router.push({ pathname: "/match/[id]", params: { id: row.matchId, date: stream?.tradeDate ?? todayCn() } })}
                  accessibilityRole="button"
                  accessibilityLabel={`${row.home} 对 ${row.away}，${row.status === "killed" ? "已砍" : "复核中"}`}
                  style={({ pressed }) => [styles.row, pressed && styles.pressed]}
                >
                  <View style={[styles.gate, { backgroundColor: tone.soft }]}>
                    <Text variant="captionStrong" color={tone.color}>
                      {row.gate === "price" ? "价" : row.gate === "market" ? "市" : row.gate === "model" ? "模" : "?"}
                    </Text>
                  </View>
                  <View style={styles.flex}>
                    <Text variant="bodyStrong" numberOfLines={1}>
                      {row.home} <Text variant="caption" color={colors.muted}>vs</Text> {row.away}
                    </Text>
                    <Text variant="caption" color={colors.muted} numberOfLines={2} style={styles.reason}>
                      {row.text}
                    </Text>
                  </View>
                  <Chip label={row.status === "killed" ? "已砍" : "复核中"} tone={row.status === "killed" ? "danger" : "amber"} />
                </Pressable>
              );
            })}
          </View>
        )}

        <Card style={styles.note}>
          <Text variant="smallStrong">不推 ≠ 不会赢</Text>
          <Text variant="caption" color={colors.muted} style={styles.noteText}>
            {copy.whyNotLead} 被砍的场次也会在赛后公开结局，砍对和砍错都写，不删历史。
          </Text>
        </Card>
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  list: { gap: spacing.sm, marginTop: spacing.base },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.base,
    minHeight: 76,
  },
  pressed: { opacity: 0.72 },
  gate: { width: 34, height: 34, borderRadius: radii.sm, alignItems: "center", justifyContent: "center" },
  flex: { flex: 1, gap: 2 },
  reason: { lineHeight: 17 },
  note: { marginTop: spacing.x4, gap: spacing.xs },
  noteText: { lineHeight: 18 },
});
