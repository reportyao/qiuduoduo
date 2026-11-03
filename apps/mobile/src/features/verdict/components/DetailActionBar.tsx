import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { VerdictDetail } from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";
import { colors, layout, spacing } from "@/theme/tokens";
import { Button, IconButton } from "@/components/ui";

interface DetailActionBarProps {
  detail: VerdictDetail;
  betExists: boolean;
  watching: boolean;
  onBet: () => void;
  onWhyNot: () => void;
  onWatch: () => void;
  onShare: () => void;
}

export function DetailActionBar({
  detail,
  betExists,
  watching,
  onBet,
  onWhyNot,
  onWatch,
  onShare,
}: DetailActionBarProps) {
  const insets = useSafeAreaInsets();
  const { copy } = usePersonaContent();
  const promoted = detail.status === "promoted";
  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
      <View style={styles.row}>
        <Button
          label={
            promoted
              ? betExists
                ? copy.bought
                : copy.buy
              : detail.status === "killed"
                ? "看死因"
                : copy.pendingCta
          }
          onPress={promoted ? onBet : onWhyNot}
          disabled={promoted && betExists}
          style={styles.primary}
        />
        <IconButton
          name={watching ? "heart" : "heart-outline"}
          onPress={onWatch}
          accessibilityLabel={watching ? "取消关注" : "关注这场比赛"}
          color={watching ? colors.danger : colors.ink}
        />
        <IconButton
          name="share-social-outline"
          onPress={onShare}
          accessibilityLabel="分享这场判断"
        />
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
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  primary: { flex: 1 },
});
