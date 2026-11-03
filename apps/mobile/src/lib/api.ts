import { createApiClient } from "@jieqiu/api-client";
import { useAuthStore } from "@/features/auth/authStore";
import { API_BASE_URL } from "./env";

/**
 * 全局唯一 API client。
 * token 由 authStore 统一管理：设备令牌不过期；手机号登录的 JWT 在到期前自动刷新。
 */
export const api = createApiClient({
  baseUrl: API_BASE_URL,
  getToken: () => useAuthStore.getState().getAccessToken(),
  getLocale: () => "zh-CN",
  getMarket: () => "cn",
});
