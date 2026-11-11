import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { VerdictDetail } from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";
import { colors, layout, spacing } from "@/theme/tokens";
import { Button, IconButton } from "@/components/ui";

interface DetailActionBarProps {
  detail: VerdictDetail;
  /** 是否已发布；false 时禁止记注，避免把复核预览当正式推荐。 */
  published?: boolean | null;
  betExists: boolean;
  watching: boolean;
  onBet: () => void;
  onWhyNot: () => void;
  onWatch: () => void;
  onShare: () => void;
  onFocus: () => void;
  onParlay: () => void;
  parlayAdded: boolean;
}

export function DetailActionBar({
  detail,
  published = null,
  betExists,
  watching,
  onBet,
  onWhyNot,
  onWatch,
  onShare,
  onFocus,
  onParlay,
  parlayAdded,
}: DetailActionBarProps) {
  const insets = useSafeAreaInsets();
  const { copy } = usePersonaContent();
  const promoted = detail.status === "promoted";
  const locked = promoted && published === false;
  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
      <Button
        label={
          locked
            ? "未发布，暂不可记"
            : promoted
              ? betExists
                ? copy.bought
                : copy.buy
              : detail.status === "killed"
                ? "看原因"
                : copy.pendingCta
        }
        onPress={promoted && !locked ? onBet : onWhyNot}
        disabled={promoted && (betExists || locked)}
        fullWidth
      />
      <View style={styles.secondaryRow}>
        <Button
          label={parlayAdded ? "已加入串关" : "加入串关"}
          variant="secondary"
          size="sm"
          onPress={onParlay}
          style={styles.parlay}
        />
        <View style={styles.icons}>
          <IconButton
            name="chatbubble-ellipses-outline"
            onPress={onFocus}
            accessibilityLabel="让助理看这场"
          />
          <IconButton
            name={watching ? "heart" : "heart-outline"}
            onPress={onWatch}
            accessibilityLabel={watching ? "取消关注" : "关注这场比赛"}
            color={watching ? colors.danger : colors.ink}
          />
          <IconButton
            name="share-social-outline"
            onPress={locked ? undefined : onShare}
            accessibilityLabel={locked ? "未发布预测，暂不可分享" : "分享这场预测"}
            color={locked ? colors.subtle : colors.ink}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
  },
  secondaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  parlay: { paddingHorizontal: spacing.sm },
  icons: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
});
