import * as Crypto from "expo-crypto";
import { create } from "zustand";
import { API_BASE_URL } from "@/lib/env";
import { ApiError, messageFromBody } from "@/lib/errors";
import type { AuthSession } from "@/domain/types";
import { readSessionRaw, writeSessionRaw } from "@/lib/sessionStorage";
import { resetLocalAccountState } from "./resetLocalState";

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
let logoutInFlight: Promise<void> | null = null;
let lastLogoutAt = 0;
// 会话代际：登录/登出/切换身份时递增；旧刷新/旧设备登录回调发现代际变化后必须丢弃结果。
let authEpoch = 0;

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
      authEpoch += 1;
      set({ session: stored });
      if (stored.mode === "jwt") {
        // 启动时就刷新一次，避免首屏批量 401；失败会转为游客身份。
        await get().getAccessToken();
      }
      if (!get().session) {
        await get().loginWithDevice().catch(() => {});
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
    // 让仍在飞的旧刷新失效，避免它在新会话建立后写回旧账号。
    authEpoch += 1;
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
      const session: AuthSession = {
        accessToken: out.access_token,
        refreshToken: out.refresh_token,
        expiresAt: Date.now() + out.expires_in * 1000,
        // 登录后不再把设备令牌当账号凭证保存；刷新失败一律回到游客/登录页。
        deviceToken: null,
        userId: out.user.user_id,
        mode: "jwt",
        displayName: out.user.display_name ?? null,
      };
      set({ session });
      await saveSession(session);
      if (get().session !== session) {
        await saveSession(get().session);
      }
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
    // 设备登录也会改动会话：同样带代际，防止 AppState/退出/登录并发时旧响应覆盖新账号。
    const epoch = ++authEpoch;
    const existing = get().session;
    const deviceToken = deviceTokenOverride ?? existing?.deviceToken ?? Crypto.randomUUID();
    const out = await requestJson<DeviceLoginResponse>("/auth/device", {
      method: "POST",
      body: JSON.stringify({ device_token: deviceToken, region: "cn" }),
    });
    if (authEpoch !== epoch) return; // 更新的登录/退出已经接管
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
    if (authEpoch !== epoch) await saveSession(get().session);
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
    const epoch = authEpoch;
    const sessionAtStart = session;
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
          ...sessionAtStart,
          accessToken: out.access_token,
          refreshToken: out.refresh_token,
          expiresAt: Date.now() + out.expires_in * 1000,
        };
        // 登录/登出已经把会话换代：丢弃旧刷新结果，绝不能把旧账号写回来。
        if (authEpoch !== epoch || get().session !== sessionAtStart) {
          return get().session?.mode === "jwt" ? get().session!.accessToken : null;
        }
        set({ session: next });
        await saveSession(next);
        // 存储写入期间若发生登出/换号，把最新会话再写回去，防止旧刷新覆盖。
        if (authEpoch !== epoch) {
          await saveSession(get().session);
          return get().session?.mode === "jwt" ? get().session!.accessToken : null;
        }
        return next.accessToken;
      } catch (error) {
        if (authEpoch !== epoch || get().session !== sessionAtStart) {
          return get().session?.mode === "jwt" ? get().session!.accessToken : null;
        }
        // 网络瞬断、5xx、429 不销毁会话；只有明确的 401/403 才视为凭证失效。
        const status = error instanceof ApiError ? error.status : 0;
        if (status === 0 || status >= 500 || status === 429) {
          return sessionAtStart.accessToken;
        }
        if (status !== 401 && status !== 403) {
          return sessionAtStart.accessToken;
        }
        set({ session: null });
        await saveSession(null);
        // JWT 不可恢复：自动创建一个新游客，保证公开判决/查询仍可用；
        // 需要账号数据时用户重新登录即可。
        try {
          await get().loginWithDevice(Crypto.randomUUID());
          return get().session?.deviceToken ?? null;
        } catch {
          return null;
        }
      } finally {
        refreshInFlight = null;
      }
    })();
    return refreshInFlight;
  },

  logout: async () => {
    if (logoutInFlight) return logoutInFlight;
    // 多个并发 410（/me、/bets、/inbox…）会在首个 logout 完成后继续到达；
    // 2 秒内复用同一次退出结果，避免连环创建多个游客账号。
    if (Date.now() - lastLogoutAt < 2000) return;
    lastLogoutAt = Date.now();
    logoutInFlight = (async () => {
      authEpoch += 1;
      refreshInFlight = null;
      const refreshToken = get().session?.refreshToken ?? null;
      // 先本地登出，避免服务端撤销请求超时把用户卡在“退出中”。
      const deviceToken = Crypto.randomUUID();
      set({ session: null });
      await saveSession(null);
      await resetLocalAccountState().catch(() => {});
      if (refreshToken) {
        void requestJson<{ ok: boolean }>("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        }).catch(() => {});
      }
      // 退出后必须是新的游客身份；复用旧设备令牌会在账号合并后把用户直接登回去。
      await get().loginWithDevice(deviceToken).catch(() => {
        set({ ready: true });
      });
    })();
    try {
      await logoutInFlight;
    } finally {
      logoutInFlight = null;
    }
  },
}));

export function isLoggedIn(session: AuthSession | null): boolean {
  return session?.mode === "jwt";
}
