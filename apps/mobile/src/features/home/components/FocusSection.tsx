import { memo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type { MatchFocus } from "@/domain/focusAdapters";
import type { VerdictSummary } from "@/domain/types";
import { Text } from "@/components/ui";
import { FocusPanel } from "./FocusPanel";
import { FocusPending } from "./FocusPending";
import { VerdictMessage } from "./ConversationMessages";
import type { FocusTarget } from "../focusStore";
import { colors, spacing } from "@/theme/tokens";

/** 首页“正在看”区块：聚焦头 + 覆盖面板 + 该场判决/待定卡片。 */
export const FocusSection = memo(function FocusSection({
  focus,
  focusData,
  focusLoading,
  focusedVerdict,
  otherCount,
  betExists,
  onOpenVerdict,
  onBet,
  onWhyNot,
  onSeal,
  onSwitch,
  onClearAll,
  onOnSale,
}: {
  focus: FocusTarget;
  focusData: MatchFocus | null | undefined;
  focusLoading: boolean;
  focusedVerdict: VerdictSummary | null;
  otherCount: number;
  betExists: boolean;
  onOpenVerdict: (id: string) => void;
  onBet: (verdict: VerdictSummary) => void;
  onWhyNot: (matchId: string) => void;
  onSeal: (id: string) => void;
  onSwitch: () => void;
  onClearAll: () => void;
  onOnSale: () => void;
}) {
  return (
    <View style={styles.focus}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text variant="overline" color={colors.brand}>正在看</Text>
          <Text variant="bodyStrong" numberOfLines={1}>
            {focus.home} vs {focus.away}
          </Text>
          <Text variant="caption" color={colors.muted}>
            {focus.matchNo} · {focus.league || "联赛待同步"}
          </Text>
        </View>
        <Pressable onPress={onSwitch} accessibilityRole="button" accessibilityLabel="换一场比赛" hitSlop={8}>
          <Text variant="captionStrong" color={colors.brand}>换一场</Text>
        </Pressable>
        <Pressable onPress={onClearAll} accessibilityRole="button" accessibilityLabel="回到今日全部" hitSlop={8}>
          <Text variant="caption" color={colors.subtle}>今日全部</Text>
        </Pressable>
      </View>

      <FocusPanel focus={focusData} loading={focusLoading} />

      {focusedVerdict ? (
        <VerdictMessage
          verdict={focusedVerdict}
          betExists={betExists}
          onOpen={onOpenVerdict}
          onBet={onBet}
          onWhyNot={onWhyNot}
          onSeal={onSeal}
        />
      ) : (
        <FocusPending
          focus={focus}
          onOpenVerdict={onOpenVerdict}
          onWhyNot={onWhyNot}
          onOnSale={onOnSale}
          onSwitch={onSwitch}
        />
      )}

      {otherCount > 0 ? (
        <Pressable
          onPress={onSwitch}
          accessibilityRole="button"
          accessibilityLabel="看今日其他比赛"
          style={styles.otherMatches}
        >
          <Text variant="caption" color={colors.muted}>
            今日其他 {otherCount} 场 · 选一场 ›
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  focus: { marginTop: spacing.base },
  head: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    paddingTop: spacing.xs,
  },
  flex: { flex: 1, gap: 1 },
  otherMatches: { alignSelf: "flex-start", paddingVertical: spacing.sm },
});
