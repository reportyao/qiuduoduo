import * as Crypto from "expo-crypto";
import { create } from "zustand";
import { API_BASE_URL } from "@/lib/env";
import { ApiError, messageFromBody } from "@/lib/errors";
import type { AuthSession } from "@/domain/types";
import { readSessionRaw, writeSessionRaw } from "@/lib/sessionStorage";

const SESSION_KEY = "jieqiu.session.v1";

interface AuthState {
  ready: boolean;
  session: AuthSession | null;
  sendingCode: boolean;
  loggingIn: boolean;
  lastError: string | null;
  bootstrap: () => Promise<void>;
  sendSmsCode: (phone: string) => Promise<string | null>;
  loginWithPhone: (phone: string, code: string) => Promise<{ merged: Record<string, number> }>;
  loginWithDevice: (deviceTokenOverride?: string) => Promise<void>;
  getAccessToken: () => Promise<string | null>;
  logout: () => Promise<void>;
}

let refreshInFlight: Promise<string | null> | null = null;

async function saveSession(session: AuthSession | null): Promise<void> {
  try {
    await writeSessionRaw(SESSION_KEY, session ? JSON.stringify(session) : null);
  } catch {
    // 存储不可用时内存态仍然可用，不因持久化失败阻塞登录。
  }
}

async function loadSession(): Promise<AuthSession | null> {
  try {
    const raw = await readSessionRaw(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (!parsed.accessToken || !parsed.mode) return null;
    return {
      accessToken: parsed.accessToken,
      refreshToken: parsed.refreshToken ?? null,
      expiresAt: typeof parsed.expiresAt === "number" ? parsed.expiresAt : null,
      deviceToken: parsed.deviceToken ?? null,
      userId: parsed.userId ?? null,
      mode: parsed.mode === "jwt" ? "jwt" : "device",
      displayName: parsed.displayName ?? null,
    };
  } catch {
    return null;
  }
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
  token?: string | null,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12_000);
  try {
    const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
    const text = await response.text();
    let body: unknown = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    if (!response.ok) {
      throw new ApiError(response.status, messageFromBody(body), body);
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, "网络连接失败，请检查网络后重试", error);
  } finally {
    clearTimeout(timer);
  }
}

interface DeviceLoginResponse {
  user_id: string;
  token: string;
  created: boolean;
  display_name: string | null;
  region: string;
}

interface PhoneLoginResponse {
  created: boolean;
  user: { user_id: string; display_name: string | null; region: string };
  access_token: string;
  refresh_token: string;
  expires_in: number;
  merged?: Record<string, number>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  ready: false,
  session: null,
  sendingCode: false,
  loggingIn: false,
  lastError: null,

  bootstrap: async () => {
    const stored = await loadSession();
    if (stored) {
      set({ session: stored });
      if (stored.mode === "jwt") {
        // 启动时就刷新一次，避免首屏批量 401；失败则保留设备身份。
        await get().getAccessToken();
      }
      set({ ready: true });
      return;
    }
    await get().loginWithDevice().catch(() => {
      // 离线首启：允许匿名浏览公开判决，登录相关页面自行提示。
      set({ ready: true });
    });
  },

  sendSmsCode: async (phone) => {
    set({ sendingCode: true, lastError: null });
    try {
      const out = await requestJson<{ ok: boolean; ttl: number; dev_code?: string }>(
        "/auth/sms/send",
        { method: "POST", body: JSON.stringify({ phone, purpose: "login" }) },
      );
      return out.dev_code ?? null;
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "验证码发送失败";
      set({ lastError: message });
      throw error;
    } finally {
      set({ sendingCode: false });
    }
  },

  loginWithPhone: async (phone, code) => {
    set({ loggingIn: true, lastError: null });
    try {
      const out = await requestJson<PhoneLoginResponse>("/auth/sms/verify", {
        method: "POST",
        body: JSON.stringify({
          phone,
          code,
          purpose: "login",
          device_token: get().session?.deviceToken ?? null,
        }),
      });
      const previousDevice = get().session?.deviceToken ?? null;
      const session: AuthSession = {
        accessToken: out.access_token,
        refreshToken: out.refresh_token,
        expiresAt: Date.now() + out.expires_in * 1000,
        deviceToken: previousDevice,
        userId: out.user.user_id,
        mode: "jwt",
        displayName: out.user.display_name ?? null,
      };
      set({ session });
      await saveSession(session);
      return { merged: out.merged ?? {} };
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "登录失败";
      set({ lastError: message });
      throw error;
    } finally {
      set({ loggingIn: false });
    }
  },

  loginWithDevice: async (deviceTokenOverride) => {
    const existing = get().session;
    const deviceToken = deviceTokenOverride ?? existing?.deviceToken ?? Crypto.randomUUID();
    const out = await requestJson<DeviceLoginResponse>("/auth/device", {
      method: "POST",
      body: JSON.stringify({ device_token: deviceToken, region: "cn" }),
    });
    const session: AuthSession = {
      accessToken: out.token,
      refreshToken: null,
      expiresAt: null,
      deviceToken: out.token,
      userId: out.user_id,
      mode: "device",
      displayName: out.display_name,
    };
    set({ session, ready: true, lastError: null });
    await saveSession(session);
  },

  getAccessToken: async () => {
    const session = get().session;
    if (!session) return null;
    if (session.mode === "device") return session.deviceToken;

    if (session.expiresAt && session.expiresAt > Date.now() + 30_000) {
      return session.accessToken;
    }
    if (!session.refreshToken) return session.accessToken;

    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      try {
        const out = await requestJson<{
          access_token: string;
          refresh_token: string;
          expires_in: number;
        }>("/auth/refresh", {
          method: "POST",
          body: JSON.stringify({ refresh_token: session.refreshToken }),
        });
        const next: AuthSession = {
          ...session,
          accessToken: out.access_token,
          refreshToken: out.refresh_token,
          expiresAt: Date.now() + out.expires_in * 1000,
        };
        set({ session: next });
        await saveSession(next);
        return next.accessToken;
      } catch {
        // 刷新失败：清掉 JWT 但保留设备令牌，用户可继续匿名使用或重新登录。
        const fallback: AuthSession | null = session.deviceToken
          ? {
              accessToken: session.deviceToken,
              refreshToken: null,
              expiresAt: null,
              deviceToken: session.deviceToken,
              userId: null,
              mode: "device",
              displayName: null,
            }
          : null;
        set({ session: fallback });
        await saveSession(fallback);
        return fallback?.deviceToken ?? null;
      } finally {
        refreshInFlight = null;
      }
    })();
    return refreshInFlight;
  },

  logout: async () => {
    const session = get().session;
    if (session?.refreshToken) {
      await requestJson<{ ok: boolean }>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: session.refreshToken }),
      }).catch(() => {});
    }
    // 退出后必须是新的游客身份；复用旧设备令牌会在账号合并后把用户直接登回去。
    const deviceToken = Crypto.randomUUID();
    set({ session: null });
    await saveSession(null);
    await get().loginWithDevice(deviceToken).catch(() => {
      set({ ready: true });
    });
  },
}));

export function isLoggedIn(session: AuthSession | null): boolean {
  return session?.mode === "jwt";
}
