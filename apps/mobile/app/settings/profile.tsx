import { useEffect, useRef, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import * as ImagePicker from "expo-image-picker";
import * as FileSystem from "expo-file-system";
import { Platform } from "react-native";
import { Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import { Avatar, Button, Card, Field, Text, useToast } from "@/components/ui";
import { PERSONAS, PERSONA_ORDER, type PersonaId } from "@/features/personas/personas";
import { usePersonaContent } from "@/features/personas/usePersona";
import { usePrefsStore } from "@/features/preferences/prefsStore";
import { useAuthStore } from "@/features/auth/authStore";
import { useMeQuery, usePatchMeMutation } from "@/features/account/queries";
import { errorText } from "@/lib/errors";
import { colors, spacing } from "@/theme/tokens";

export default function ProfileScreen() {
  const router = useRouter();
  const toast = useToast();
  const { meta } = usePersonaContent();
  const session = useAuthStore((s) => s.session);
  const meQuery = useMeQuery(Boolean(session?.userId));
  const patchMe = usePatchMeMutation();
  const setPersona = usePrefsStore((s) => s.setPersona);
  const avatarUri = usePrefsStore((s) => s.avatarUri);
  const setAvatarUri = usePrefsStore((s) => s.setAvatarUri);
  const [name, setName] = useState("");
  const dirty = useRef(false);
  const mounted = useRef(true);
  const me = meQuery.data;

  useEffect(() => () => { mounted.current = false; }, []);

  useEffect(() => {
    if (me?.displayName && !dirty.current) setName(me.displayName);
  }, [me?.displayName]);

  const chooseAvatar = async (id: PersonaId) => {
    if (id === meta.id) return;
    const previous = meta.id;
    setPersona(id);
    if (session?.mode === "jwt") {
      try {
        await patchMe.mutateAsync({ persona: id });
      } catch (e) {
        setPersona(previous);
        toast.show(errorText(e), "error");
      }
    }
  };

  const save = async () => {
    const trimmed = name.trim();
    if (trimmed.length < 1 || trimmed.length > 12) {
      toast.show("昵称需要 1–12 个字", "warning");
      return;
    }
    try {
      await patchMe.mutateAsync({ displayName: trimmed });
      dirty.current = false;
      toast.show("资料已保存", "success");
      if (mounted.current) goBackOr(router);
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  return (
    <SettingsPage title="个人资料" subtitle="昵称与头像" onBack={() => goBackOr(router)}>
      <Card style={styles.card}>
        <Text variant="overline" color={colors.green}>头像</Text>
        <View style={styles.currentRow}>
          <Avatar source={avatarUri ? { uri: avatarUri } : meta.avatar} fallbackSource={meta.avatar} size={64} online />
          <View style={styles.flex}>
            <Text variant="smallStrong">当前头像</Text>
            <Text variant="caption" color={colors.muted} style={styles.note}>
              {avatarUri ? "使用你上传的照片，只保存在本机。" : "跟随助理形象；也可以从相册上传。"}
            </Text>
          </View>
        </View>
        <View style={styles.uploadRow}>
          <Button
            label="从相册上传"
            variant="secondary"
            size="sm"
            onPress={async () => {
              const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
              if (!permission.granted) {
                toast.show("需要相册权限才能选择头像", "warning");
                return;
              }
              const result = await ImagePicker.launchImageLibraryAsync({
                mediaTypes: ImagePicker.MediaTypeOptions.Images,
                allowsEditing: true,
                aspect: [1, 1],
                quality: 0.8,
              });
              if (!result.canceled && result.assets[0]?.uri) {
                const picked = result.assets[0].uri;
                let saved = picked;
                if (Platform.OS !== "web" && FileSystem.documentDirectory) {
                  try {
                    const dir = `${FileSystem.documentDirectory}avatars/`;
                    await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
                    const dest = `${dir}avatar-${Date.now()}.jpg`;
                    await FileSystem.copyAsync({ from: picked, to: dest });
                    if (avatarUri?.startsWith(dir)) {
                      await FileSystem.deleteAsync(avatarUri, { idempotent: true });
                    }
                    saved = dest;
                  } catch {
                    // 复制失败仍可用 picker 临时 URI，但下次启动可能被系统清理。
                  }
                }
                setAvatarUri(saved);
                toast.show("头像已更新，只保存在本机", "success");
              }
            }}
            style={styles.flex}
          />
          {avatarUri ? (
            <Button
              label="恢复助理形象"
              variant="ghost"
              size="sm"
              onPress={async () => {
                if (Platform.OS !== "web" && avatarUri && FileSystem.documentDirectory) {
                  const dir = `${FileSystem.documentDirectory}avatars/`;
                  if (avatarUri.startsWith(dir)) {
                    await FileSystem.deleteAsync(avatarUri, { idempotent: true }).catch(() => {});
                  }
                }
                setAvatarUri(null);
              }}
              style={styles.flex}
            />
          ) : null}
        </View>
        <View style={styles.avatars}>
          {PERSONA_ORDER.map((id) => (
            <Pressable
              key={id}
              onPress={() => chooseAvatar(id)}
              accessibilityRole="radio"
              accessibilityLabel={PERSONAS[id].name}
              accessibilityState={{ selected: meta.id === id }}
              style={[styles.avatarOption, meta.id === id && styles.avatarSelected]}
            >
              <Avatar source={PERSONAS[id].avatar} size={58} />
            </Pressable>
          ))}
        </View>
        <Text variant="caption" color={colors.muted} style={styles.note}>
          选择下方助理形象会同时改变首页顶部形象和说话方式；上传照片只改你的个人头像。
        </Text>
      </Card>

      <Card style={styles.card}>
        <Field
          label="昵称"
          value={name}
          onChangeText={(value) => { dirty.current = true; setName(value); }}
          maxLength={12}
          hint="1–12 个字，随时可改。"
          placeholder="怎么称呼你？"
        />
      </Card>

      <Card style={styles.card}>
        <Text variant="overline" color={colors.green}>账号</Text>
        <Row label="手机号 / 邮箱" value={me?.phone ?? me?.email ?? "未绑定"} />
        <Row label="登录方式" value={session?.mode === "jwt" ? "手机号" : "设备账户"} />
        <Row label="地区" value={me?.region === "global" ? "国际" : "中国"} />
      </Card>

      <Button label="保存" onPress={save} loading={patchMe.isPending} fullWidth />
      <Button label="取消" variant="ghost" onPress={() => router.back()} fullWidth />
      <Text variant="caption" color={colors.subtle} center style={styles.note}>
        球多多不会收集你的出生日期，也不会上传通讯录。
      </Text>
    </SettingsPage>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text variant="small" color={colors.muted}>{label}</Text>
      <Text variant="smallStrong">{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { gap: spacing.sm },
  currentRow: { flexDirection: "row", alignItems: "center", gap: spacing.base },
  flex: { flex: 1 },
  uploadRow: { flexDirection: "row", gap: spacing.sm },
  avatars: { flexDirection: "row", gap: spacing.base },
  avatarOption: {
    padding: 4,
    borderRadius: 40,
    borderWidth: 2,
    borderColor: "transparent",
  },
  avatarSelected: { borderColor: colors.green },
  note: { lineHeight: 18 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
});
