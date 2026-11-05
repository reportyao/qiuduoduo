import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { goBackOr } from "@/lib/navigation";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import { Card, Icon, SettingsGroup, SettingsRow, Text, useToast } from "@/components/ui";
import type { OddsFormat } from "@/features/preferences/prefsStore";
import { useOddsFormat, usePrefsStore } from "@/features/preferences/prefsStore";
import { useAuthStore } from "@/features/auth/authStore";
import { usePatchMeMutation } from "@/features/account/queries";
import { decimalToFormat, oddsFormatLabel } from "@/lib/format";
import { errorText } from "@/lib/errors";
import { colors, radii, spacing } from "@/theme/tokens";

const FORMATS: { id: OddsFormat; example: string; hint: string }[] = [
  { id: "decimal", example: decimalToFormat(2.05, "decimal"), hint: "含本金，国际通用" },
  { id: "hk", example: decimalToFormat(2.05, "hk"), hint: "不含本金，香港常用" },
  { id: "indo", example: decimalToFormat(2.05, "indo"), hint: "低赔为负数，印尼常用" },
  { id: "american", example: decimalToFormat(2.05, "american"), hint: "正负号，美国常用" },
];

export default function PreferencesScreen() {
  const router = useRouter();
  const toast = useToast();
  const current = useOddsFormat();
  const setOddsFormat = usePrefsStore((s) => s.setOddsFormat);
  const session = useAuthStore((s) => s.session);
  const patchMe = usePatchMeMutation();
  const [saving, setSaving] = useState(false);

  const choose = async (format: OddsFormat) => {
    if (format === current || saving) return;
    const previous = current;
    setSaving(true);
    setOddsFormat(format);
    try {
      if (session?.mode === "jwt") await patchMe.mutateAsync({ oddsFormat: format });
      toast.show(`已切换为${oddsFormatLabel(format)}`, "success");
    } catch (e) {
      setOddsFormat(previous);
      toast.show(errorText(e), "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsPage title="偏好" subtitle="赔率格式与语言" onBack={() => goBackOr(router)}>
      <Text variant="overline" color={colors.green}>赔率格式</Text>
      <Text variant="small" color={colors.muted} style={styles.lead}>
        只改显示方式，不改变赔率本身。以欧洲盘 2.05 为例：
      </Text>
      <View style={styles.list}>
        {FORMATS.map((format) => {
          const selected = current === format.id;
          return (
            <Pressable
              key={format.id}
              onPress={() => choose(format.id)}
              disabled={saving}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={oddsFormatLabel(format.id)}
              style={({ pressed }) => [styles.row, selected && styles.selected, pressed && styles.pressed]}
            >
              <View style={styles.flex}>
                <Text variant="bodyStrong">{oddsFormatLabel(format.id)}</Text>
                <Text variant="caption" color={colors.muted}>{format.hint}</Text>
              </View>
              <Text variant="h3" color={selected ? colors.green : colors.ink}>{format.example}</Text>
              {selected ? <Icon name="checkmark-circle" size={18} color={colors.green} /> : null}
            </Pressable>
          );
        })}
      </View>

      <SettingsGroup title="语言">
        <SettingsRow
          title="界面语言"
          subtitle="当前仅提供简体中文；英文随国际版开放"
          value="中文"
          icon="language-outline"
          last
        />
      </SettingsGroup>
      <Card style={styles.noteCard}>
        <Text variant="smallStrong">文案按人设分离</Text>
        <Text variant="caption" color={colors.muted} style={styles.note}>
          切换助理风格时，按钮、卡片和预测语气会一起变，但数字不会。
        </Text>
      </Card>
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  lead: { lineHeight: 20, marginTop: -spacing.xs },
  list: { gap: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.base,
  },
  selected: { borderColor: colors.green, backgroundColor: colors.greenSoft },
  pressed: { opacity: 0.8 },
  flex: { flex: 1, gap: 2 },
  noteCard: { gap: spacing.xs },
  note: { lineHeight: 19 },
});
