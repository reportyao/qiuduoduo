import { useEffect, useRef, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, usePathname, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AppState, StyleSheet, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { BootScreen } from "@/components/BootScreen";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/ui/Toast";
import { useAuthStore } from "@/features/auth/authStore";
import { useMeQuery } from "@/features/account/queries";
import { useComplianceStore, isExcluded } from "@/features/compliance/complianceStore";
import { useComplianceSync } from "@/features/compliance/useComplianceSync";
import { usePrefsStore } from "@/features/preferences/prefsStore";
import { usePushRegistration } from "@/features/push/usePushRegistration";
import { makeQueryClient } from "@/lib/queryClient";
import { useNow } from "@/lib/useNow";
import { colors } from "@/theme/tokens";

/**
 * 根布局只做四件事：
 * 1) 提供 QueryClient / SafeArea / Toast；
 * 2) 水合本地偏好与合规状态、恢复登录态；
 * 3) 路由守卫（年龄门 / 未成年 / 自排除）；
 * 4) 登录后把服务端人设与赔率格式同步到本地。
 */
export default function RootLayout() {
  const [queryClient] = useState(makeQueryClient);
  const ready = useAuthStore((s) => s.ready);
  const sessionKey = useAuthStore((s) =>
    s.session ? `${s.session.userId ?? "anon"}:${s.session.mode}` : "none",
  );
  const prefsHydrated = usePrefsStore((s) => s.hydrated);
  const complianceHydrated = useComplianceStore((s) => s.hydrated);

  useEffect(() => {
    void usePrefsStore.getState().hydrate();
    void useComplianceStore.getState().hydrate();
    void useAuthStore.getState().bootstrap();
  }, []);

  const booted = ready && prefsHydrated && complianceHydrated;

  // 深链可能在设备身份就绪前就发了请求（401）。身份变化后统一重取，避免缓存首屏假错误。
  useEffect(() => {
    if (!booted) return;
    void queryClient.invalidateQueries();
  }, [booted, queryClient, sessionKey]);

  // 弱网首启可能没拿到设备身份；回到前台时补一次恢复，避免整场会话都 401。
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "active") return;
      const auth = useAuthStore.getState();
      const task = auth.session ? auth.getAccessToken() : auth.loginWithDevice();
      void task.then(() => queryClient.invalidateQueries()).catch(() => {});
    });
    return () => sub.remove();
  }, [queryClient]);

  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
        <StatusBar style="dark" backgroundColor={colors.bg} />
        <ToastProvider>
          <View style={styles.fill}>
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: styles.root,
                animation: "slide_from_right",
              }}
            >
              <Stack.Screen name="(tabs)" options={{ animation: "none" }} />
              <Stack.Screen name="onboarding" options={{ animation: "fade" }} />
              <Stack.Screen
                name="assistant"
                options={{ presentation: "modal", animation: "slide_from_bottom" }}
              />
            </Stack>
            {booted ? (
              <>
                <ProfileSync />
                <ComplianceSync />
                <PushRegistration />
                <RouteGuard />
              </>
            ) : (
              <View style={StyleSheet.absoluteFill}>
                <BootScreen />
              </View>
            )}
          </View>
          </ToastProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}

function RouteGuard() {
  const router = useRouter();
  const pathname = usePathname();
  const ageDecision = usePrefsStore((s) => s.ageDecision);
  const excludedUntil = useComplianceStore((s) => s.excludedUntil);
  const excludedPermanent = useComplianceStore((s) => s.excludedPermanent);
  const now = useNow(30_000);
  const excluded = excludedPermanent || isExcluded(excludedUntil, now);

  useEffect(() => {
    const isOnboarding = pathname.startsWith("/onboarding");
    const isLegal = pathname.startsWith("/legal");
    const isHelp = pathname.startsWith("/settings/compliance");
    const isMinorPage = pathname.startsWith("/minor");
    const isPaused = pathname.startsWith("/paused");
    const isPublicLedger = pathname.startsWith("/records/ledger");

    if (ageDecision === "unknown" && !isOnboarding && !isLegal) {
      router.replace("/onboarding");
      return;
    }
    if (ageDecision === "minor" && !isMinorPage && !isOnboarding && !isLegal && !isPublicLedger) {
      router.replace("/minor");
      return;
    }
    if (ageDecision === "adult" && excluded && !isPaused && !isLegal && !isHelp && !isOnboarding) {
      router.replace("/paused");
    }
  }, [ageDecision, excluded, pathname, router]);

  return null;
}

function ComplianceSync() {
  useComplianceSync();
  return null;
}

function PushRegistration() {
  usePushRegistration();
  return null;
}

/** 已登录用户以服务端设置为主；设备游客保留本机选择，不被默认值覆盖。 */
function ProfileSync() {
  const session = useAuthStore((s) => s.session);
  const setPersona = usePrefsStore((s) => s.setPersona);
  const setOddsFormat = usePrefsStore((s) => s.setOddsFormat);
  const appliedFor = useRef<string | null>(null);
  const { data } = useMeQuery(Boolean(session?.userId));
  const isJwt = session?.mode === "jwt";

  useEffect(() => {
    if (!isJwt) appliedFor.current = null;
  }, [isJwt]);

  useEffect(() => {
    if (!isJwt || !data || appliedFor.current === data.userId) return;
    appliedFor.current = data.userId;
    setPersona(data.persona);
    setOddsFormat(data.oddsFormat);
  }, [data, isJwt, setOddsFormat, setPersona]);

  return null;
}

const styles = StyleSheet.create({
  root: { backgroundColor: colors.bg },
  fill: { flex: 1 },
});
