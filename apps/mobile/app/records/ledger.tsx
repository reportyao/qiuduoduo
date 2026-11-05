import { useMemo, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import * as Clipboard from "expo-clipboard";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  Sheet,
  Skeleton,
  Text,
  useToast,
} from "@/components/ui";
import { useLedgerQuery } from "@/features/records/queries";
import { ledgerStatusLabel } from "@/features/records/ledgerStatus";
import { usePersonaContent } from "@/features/personas/usePersona";
import { errorText } from "@/lib/errors";
import { shortHash } from "@/lib/format";
import { pickDirectionLabel } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Filter = "all" | "win" | "lose";

export default function LedgerScreen() {
  const router = useRouter();
  const toast = useToast();
  const { copy } = usePersonaContent();
  const query = useLedgerQuery();
  const [filter, setFilter] = useState<Filter>("all");
  const [verifyOpen, setVerifyOpen] = useState(false);

  const items = useMemo(() => {
    const list = query.data?.items ?? [];
    if (filter === "win") return list.filter((item) => item.settled === "win");
    if (filter === "lose") return list.filter((item) => item.settled === "lose");
    return list;
  }, [filter, query.data]);
  const stats = query.data?.stats;

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="公开账本"
        subtitle="输赢与连败都公开"
        showAssistant={false}
        onBack={() => goBackOr(router)}
        right={<Chip label="可复算" tone="green" />}
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Text variant="overline" color={colors.green}>F14 · 不删历史</Text>
        <Text variant="display" style={styles.title}>赢的写，输的也写</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>
          每条预测赛前封存 SHA-256。任何一条都能独立复算，连败也公开。
        </Text>

        <View style={styles.stats}>
          <Stat label="通过三关" value={String(stats?.promotedTotal ?? 0)} />
          <Stat label="已结算" value={String(stats?.settled ?? 0)} />
          <Stat label="中 / 未中" value={`${stats?.wins ?? 0} / ${stats?.losses ?? 0}`} />
          <Stat label="当前连败" value={String(stats?.currentLosingStreak ?? 0)} tone="danger" />
        </View>

        <View style={styles.filters}>
          {([
            ["all", "全部"],
            ["win", "命中"],
            ["lose", "未中"],
          ] as [Filter, string][]).map(([key, label]) => (
            <Chip key={key} label={label} selected={filter === key} onPress={() => setFilter(key)} />
          ))}
          <Pressable onPress={() => setVerifyOpen(true)} hitSlop={6}>
            <Text variant="captionStrong" color={colors.green}>如何验证</Text>
          </Pressable>
        </View>

        {query.isLoading ? (
          <View style={{ gap: spacing.sm }}>
            <Skeleton height={76} radius={16} />
            <Skeleton height={76} radius={16} />
            <Skeleton height={76} radius={16} />
          </View>
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            icon="book-outline"
            title="账本还是空的"
            body="还没有已公开的预测。等第一批预测产生，这里会按时间倒序出现。"
            actionLabel="看今日预测"
            onAction={() => router.push("/(tabs)")}
          />
        ) : (
          <Card padded={false}>
            {items.map((item, index) => (
              <Pressable
                key={item.id}
                onPress={() => router.push({ pathname: "/verdict/[id]", params: { id: item.id } })}
                accessibilityRole="button"
                accessibilityLabel={`${item.match}，${ledgerStatusLabel(item.status)}，${
                  item.settled === "win" ? "已命中" : item.settled === "lose" ? "未命中" : "待结算"
                }`}
                style={({ pressed }) => [
                  styles.row,
                  index < items.length - 1 && styles.rowLine,
                  pressed && styles.pressed,
                ]}
              >
                <View style={styles.dateCol}>
                  <Text variant="caption" color={colors.subtle}>{item.tradeDate.slice(5)}</Text>
                  <Text variant="caption" color={colors.subtle}>{item.matchNo}</Text>
                </View>
                <View style={styles.flex}>
                  <Text variant="bodyStrong" numberOfLines={1}>{item.match}</Text>
                  <Text
                    variant="caption"
                    color={item.status === "killed" ? colors.danger : colors.muted}
                  >
                    {ledgerStatusLabel(item.status)} ·{" "}
                    {item.pick?.dir ? pickDirectionLabel(item.pool, item.pick.dir) : "未给方向"}
                    {item.resultScore ? ` · ${item.resultScore}` : ""}
                  </Text>
                  <Text variant="mono" color={colors.subtle}>{shortHash(item.hash, 10, 6)}</Text>
                </View>
                <Chip
                  label={item.settled === "win" ? "✓ 中" : item.settled === "lose" ? "× 未中" : "待定"}
                  tone={item.settled === "win" ? "green" : item.settled === "lose" ? "danger" : "neutral"}
                />
              </Pressable>
            ))}
          </Card>
        )}

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>{copy.footer}</Text>
      </ScrollView>

      <Sheet
        visible={verifyOpen}
        onClose={() => setVerifyOpen(false)}
        title="如何独立验证"
        subtitle="不需要相信球多多，自己算。"
        footer={
          <Button
            label="复制验证命令"
            variant="secondary"
            icon="copy-outline"
            onPress={async () => {
              await Clipboard.setStringAsync(
                `python3 -c "import json,hashlib;p=json.load(open('payload.json'));print(hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())"`,
              );
              toast.show("命令已复制", "success");
            }}
            fullWidth
          />
        }
      >
        <Text variant="small" color={colors.muted} style={styles.verifyText}>
          1. 打开任意一条预测，点「封存与验证」。
        </Text>
        <Text variant="small" color={colors.muted} style={styles.verifyText}>
          2. 复制封存原文（payload.json）。
        </Text>
        <Text variant="small" color={colors.muted} style={styles.verifyText}>
          3. 用 canonical JSON 做 SHA-256，比较封存哈希。改一个字都对不上。
        </Text>
        <Text variant="caption" color={colors.subtle} style={styles.verifyText}>
          公开账本里的哈希前 10 位与封存页一致。链锚点可由 /chain/verify 与 /anchor/latest 独立校验。
        </Text>
      </Sheet>
    </AppScreen>
  );
}

function Stat({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" }) {
  return (
    <View style={styles.stat}>
      <Text variant="caption" color={colors.muted}>{label}</Text>
      <Text variant="h3" color={tone === "danger" ? colors.danger : colors.ink}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  stats: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.base },
  stat: {
    flexGrow: 1,
    flexBasis: "22%",
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.sm,
    gap: 1,
  },
  filters: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginTop: spacing.base, marginBottom: spacing.sm, flexWrap: "wrap" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.base,
    minHeight: 76,
  },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  pressed: { backgroundColor: colors.bgElevated },
  dateCol: { width: 44, gap: 1 },
  flex: { flex: 1, gap: 1 },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
  verifyText: { lineHeight: 21, marginBottom: spacing.xs },
});
