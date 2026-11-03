import { createApiClient } from "@jieqiu/api-client";
import { API_BASE_URL } from "./env";

// 后续接入 SecureStore 读取 access token；MVP 阶段先支持设备令牌。
let token: string | null = null;

export function setApiToken(value: string | null) {
  token = value;
}

export const api = createApiClient({
  baseUrl: API_BASE_URL,
  getToken: () => token,
  getLocale: () => "zh-CN",
  getMarket: () => "cn",
});
