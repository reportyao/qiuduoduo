import { useEffect, useRef, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Field, Text, useToast } from "@/components/ui";
import { useAuthStore, isLoggedIn } from "@/features/auth/authStore";
import { errorText } from "@/lib/errors";
import { colors, layout, spacing } from "@/theme/tokens";

export default function LoginScreen() {
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const session = useAuthStore((s) => s.session);
  const sendCode = useAuthStore((s) => s.sendSmsCode);
  const login = useAuthStore((s) => s.loginWithPhone);
  const loggingIn = useAuthStore((s) => s.loggingIn);
  const sending = useAuthStore((s) => s.sendingCode);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const autoBack = useRef(isLoggedIn(session));

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  useEffect(() => {
    if (autoBack.current && isLoggedIn(session)) {
      // 只有“进入页面时已登录”才自动返回；提交登录后的跳转由 submit 统一处理。
      const timer = setTimeout(() => {
        autoBack.current = false;
        goBackOr(router);
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [router, session]);

  const requestCode = async () => {
    setError(null);
    if (!/^1\d{10}$/.test(phone)) {
      setError("请输入中国大陆 11 位手机号");
      return;
    }
    try {
      const devCode = await sendCode(phone);
      setCooldown(60);
      if (devCode) {
        setCode(devCode);
        toast.show(`开发环境验证码 ${devCode} 已填入`, "info");
      } else {
        toast.show("验证码已发送", "success");
      }
    } catch (e) {
      setError(errorText(e));
    }
  };

  const submit = async () => {
    setError(null);
    if (!/^1\d{10}$/.test(phone)) {
      setError("请输入正确的手机号");
      return;
    }
    if (code.trim().length < 4) {
      setError("请输入验证码");
      return;
    }
    try {
      autoBack.current = false;
      const result = await login(phone, code.trim());
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      const merged = result.merged;
      toast.show(
        merged.bets
          ? `登录成功，已合并 ${merged.bets} 注历史记录`
          : "登录成功，资料已同步",
        "success",
      );
      goBackOr(router);
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader title="登录 / 注册" showAssistant={false} onBack={() => goBackOr(router)} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text variant="overline" color={colors.green}>手机号验证码</Text>
          <Text variant="display" style={styles.title}>登录后，账跟着你</Text>
          <Text variant="body" color={colors.muted} style={styles.lead}>
            设备账户也可以直接使用；绑定手机号后，换手机不会丢注单和记忆。
          </Text>

          <Card style={styles.form}>
            <Field
              label="手机号"
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              maxLength={11}
              placeholder="11 位手机号"
              autoComplete="tel"
            />
            <Field
              label="验证码"
              value={code}
              onChangeText={setCode}
              keyboardType="number-pad"
              maxLength={6}
              placeholder="6 位验证码"
              right={
                <Button
                  label={cooldown > 0 ? `${cooldown}s` : "获取验证码"}
                  variant="ghost"
                  size="sm"
                  onPress={requestCode}
                  loading={sending}
                  disabled={cooldown > 0}
                />
              }
            />
            {error ? <Text variant="caption" color={colors.danger}>{error}</Text> : null}
            <Button
              label={loggingIn ? "正在登录…" : "登录 / 注册"}
              onPress={submit}
              loading={loggingIn}
              disabled={!phone || !code}
              fullWidth
            />
          </Card>

          <Text variant="caption" color={colors.subtle} center style={styles.altLogin}>
            微信 / Google / Apple 登录将在对应渠道包开放
          </Text>

          <Text variant="caption" color={colors.subtle} center style={styles.footer}>
            继续即表示你已阅读
            <Text
              variant="caption"
              color={colors.green}
              accessibilityRole="link"
              onPress={() => router.push({ pathname: "/legal", params: { doc: "terms" } })}
            >
              《服务说明》
            </Text>
            和
            <Text
              variant="caption"
              color={colors.green}
              accessibilityRole="link"
              onPress={() => router.push({ pathname: "/legal", params: { doc: "privacy" } })}
            >
              《隐私政策》
            </Text>
            。未满 18 周岁禁止购彩。
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.x4, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  form: { marginTop: spacing.x4, gap: spacing.base },
  altLogin: { marginTop: spacing.base, lineHeight: 17 },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
});
