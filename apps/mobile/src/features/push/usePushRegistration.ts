import { useEffect, useRef } from "react";
import Constants from "expo-constants";
import { Platform } from "react-native";
import { useAuthStore } from "@/features/auth/authStore";
import { useRegisterPushMutation } from "@/features/inbox/queries";
import { getJPushRegistrationId, initializeJPush } from "./jpush";

/**
 * Register the JPush registration id with our account after boot.
 * JPush can take a few seconds to connect, so poll briefly instead of assuming
 * the first read is ready.
 */
export function usePushRegistration(): void {
  const userId = useAuthStore((s) => s.session?.userId ?? null);
  const { mutateAsync: registerPush } = useRegisterPushMutation();
  const lastToken = useRef("");

  useEffect(() => {
    if (Platform.OS !== "android" || !userId) return;
    lastToken.current = "";
    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      if (cancelled) return;
      const token = await getJPushRegistrationId();
      if (token) {
        if (token !== lastToken.current) {
          try {
            await registerPush({
              token,
              appVersion: Constants.expoConfig?.version ?? "0.3.0",
            });
            lastToken.current = token;
            console.info("[push] registration synced");
          } catch (error) {
            console.warn("[push] registration sync failed", error);
          }
        }
        return;
      }
      attempts += 1;
      if (attempts < 30) timer = setTimeout(() => void tick(), 2000);
    };

    void initializeJPush().then(tick);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [registerPush, userId]);
}
