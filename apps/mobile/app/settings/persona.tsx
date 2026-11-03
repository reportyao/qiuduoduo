import { Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import { Avatar, Button, Card, Icon, Text, useToast } from "@/components/ui";
import { PERSONAS, PERSONA_ORDER, type PersonaId } from "@/features/personas/personas";
import { usePersonaContent } from "@/features/personas/usePersona";
import { usePrefsStore } from "@/features/preferences/prefsStore";
import { useAuthStore } from "@/features/auth/authStore";
import { usePatchMeMutation } from "@/features/account/queries";
import { errorText } from "@/lib/errors";
import { colors, radii, spacing } from "@/theme/tokens";

export default function PersonaScreen() {
  const router = useRouter();
  const toast = useToast();
  const { id: current, meta, copy } = usePersonaContent();
  const setPersona = usePrefsStore((s) => s.setPersona);
  const session = useAuthStore((s) => s.session);
  const patchMe = usePatchMeMutation();

  const select = async (id: PersonaId) => {
    if (id === current) return;
    const previous = current;
    setPersona(id);
    if (session?.mode === "jwt") {
      try {
        await patchMe.mutateAsync({ persona: id });
      } catch (e) {
        setPersona(previous);
        toast.show(errorText(e), "error");
        return;
      }
    }
    toast.show(`已切换为${PERSONAS[id].name}，文案立即生效`, "success");
  };

  return (
    <SettingsPage title="助理风格" subtitle="只改语气，不改判断" onBack={() => router.back()}>
      <Card style={styles.intro}>
        <Text variant="h3">选一个说话方式</Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          同一组数字，不同说法。人设只影响语气，不影响概率、三关结果和封存内容。
        </Text>
      </Card>

      <View style={styles.list}>
        {PERSONA_ORDER.map((id) => {
          const persona = PERSONAS[id];
          const selected = current === id;
          return (
            <Pressable
              key={id}
              onPress={() => select(id)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={persona.name}
              style={({ pressed }) => [
                styles.row,
                selected && styles.selected,
                pressed && styles.pressed,
              ]}
            >
              <Avatar source={persona.avatar} size={54} ring={selected} />
              <View style={styles.flex}>
                <View style={styles.titleRow}>
                  <Text variant="bodyStrong">{persona.name}</Text>
                  {selected ? <Icon name="checkmark-circle" size={18} color={colors.green} /> : null}
                </View>
                <Text variant="caption" color={colors.muted}>{persona.tag}</Text>
                <Text variant="small" color={colors.muted} style={styles.sample}>
                  「{persona.sample}」
                </Text>
              </View>
            </Pressable>
          );
        })}
      </View>

      <Card tone="green" style={styles.preview}>
        <Text variant="overline" color={colors.green}>预览 · 今晚的结论会这样说</Text>
        <Text variant="body" color={colors.ink} style={styles.paragraph}>
          {meta.sample}
        </Text>
        <Text variant="caption" color={colors.muted}>
          当前：{meta.name} · {meta.tag}
        </Text>
      </Card>

      <Button label="完成" onPress={() => router.back()} fullWidth />
      <Text variant="caption" color={colors.subtle} center style={styles.footer}>
        {copy.footer}
      </Text>
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  intro: { gap: spacing.xs },
  paragraph: { lineHeight: 21 },
  list: { gap: spacing.sm },
  row: {
    flexDirection: "row",
    gap: spacing.base,
    backgroundColor: colors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.base,
    alignItems: "center",
  },
  selected: { borderColor: colors.green, backgroundColor: colors.greenSoft },
  pressed: { opacity: 0.8 },
  flex: { flex: 1, gap: 2 },
  titleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sample: { lineHeight: 18, marginTop: 2 },
  preview: { gap: spacing.xs },
  footer: { lineHeight: 18, paddingHorizontal: spacing.base },
});
