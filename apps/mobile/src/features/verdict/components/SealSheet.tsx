import * as Clipboard from "expo-clipboard";
import { ScrollView, StyleSheet, View } from "react-native";
import { colors, radii, spacing, type } from "@/theme/tokens";
import { useSealQuery } from "@/features/verdict/queries";
import { shortHash } from "@/lib/format";
import { Button, ErrorState, KeyValueRow, Sheet, Skeleton, Text, useToast } from "@/components/ui";
import { Icon } from "@/components/ui";
import { haptic } from "@/lib/haptics";

interface SealSheetProps {
  visible: boolean;
  verdictId: string | null;
  sealed?: boolean;
  onClose: () => void;
}

export function SealSheet({ visible, verdictId, sealed = true, onClose }: SealSheetProps) {
  const query = useSealQuery(verdictId ?? undefined, visible);
  const toast = useToast();
  const seal = query.data;

  const copyHash = async () => {
    if (!seal) return;
    await Clipboard.setStringAsync(seal.storedHash);
    haptic("light");
    toast.show("完整哈希已复制", "success");
  };

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      title="封存与验证"
      subtitle="预测赛前封存。改一个字，哈希就对不上。"
      footer={
        seal ? (
          <Button label="复制完整哈希" variant="secondary" icon="copy-outline" onPress={copyHash} fullWidth />
        ) : null
      }
    >
      {query.isLoading ? (
        <View style={{ gap: spacing.sm }}>
          <Skeleton height={58} radius={14} />
          <Skeleton height={110} radius={14} />
          <Skeleton height={160} radius={14} />
        </View>
      ) : query.isError ? (
        <ErrorState message="封存详情暂时取不到，可能是网络问题。" onRetry={() => query.refetch()} />
      ) : seal ? (
        <>
          <View
            style={[
              styles.verify,
              !sealed ? styles.verifyPending : seal.match ? styles.verifyOk : styles.verifyBad,
            ]}
          >
            <Icon
              name={!sealed ? "time-outline" : seal.match ? "shield-checkmark" : "alert-circle"}
              size={22}
              color={!sealed ? colors.amber : seal.match ? colors.green : colors.danger}
            />
            <View style={styles.flex}>
              <Text
                variant="bodyStrong"
                color={!sealed ? colors.amber : seal.match ? colors.green : colors.danger}
              >
                {!sealed
                  ? "尚未封存 · 当前载荷预览"
                  : seal.match
                    ? "自检通过 · 哈希一致"
                    : "自检失败 · 内容被改动过"}
              </Text>
              <Text variant="caption" color={colors.muted}>
                {seal.algorithm} · {seal.revisionCount} 次修订
              </Text>
            </View>
          </View>

          <View style={styles.kvBlock}>
            <KeyValueRow label="封存哈希" value={shortHash(seal.storedHash, 12, 10)} />
            <KeyValueRow label="复算哈希" value={shortHash(seal.recomputedHash, 12, 10)} />
            <KeyValueRow label="链上位置" value={shortHash(seal.chain.hash, 10, 8)} last />
          </View>

          <Text variant="captionStrong" color={colors.muted} style={styles.label}>封存原文</Text>
          <ScrollView style={styles.payload} nestedScrollEnabled>
            <Text variant="mono" style={styles.payloadText} selectable>
              {JSON.stringify(seal.payload, null, 2)}
            </Text>
          </ScrollView>

          <Text variant="caption" color={colors.muted} style={styles.hint}>
            验证方法：把上面原文按 canonical JSON 重新 SHA-256，结果必须等于封存哈希。
          </Text>
          {seal.verifyHint ? (
            <Text variant="mono" color={colors.subtle} style={styles.hint} selectable>
              {seal.verifyHint}
            </Text>
          ) : null}
        </>
      ) : null}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  verify: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
    padding: spacing.base,
    borderRadius: radii.md,
    marginBottom: spacing.base,
  },
  verifyOk: { backgroundColor: colors.greenSoft },
  verifyBad: { backgroundColor: colors.dangerSoft },
  verifyPending: { backgroundColor: colors.amberSoft },
  kvBlock: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    paddingHorizontal: spacing.base,
  },
  label: { marginTop: spacing.base, marginBottom: spacing.xs },
  payload: {
    maxHeight: 180,
    backgroundColor: colors.heroBottom,
    borderRadius: radii.md,
    padding: spacing.base,
  },
  payloadText: {
    color: colors.greenAccent,
    fontSize: type.caption.fontSize,
    lineHeight: 17,
    fontFamily: "monospace",
  },
  hint: { marginTop: spacing.sm, lineHeight: 18 },
});
