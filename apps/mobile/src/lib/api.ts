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
  onError: (status) => {
    // 注销冷静期（410）任何页面都不该继续以原账号身份请求；统一退回游客。
    if (status === 410) {
      void useAuthStore.getState().logout();
    }
    // 设备令牌/JWT 被服务端拒绝时不能永久卡在 401；退出会单飞创建一个新游客。
    if (status === 401 && useAuthStore.getState().session) {
      void useAuthStore.getState().logout();
    }
  },
});
