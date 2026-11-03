import { Platform } from "react-native";
import { devApiBaseUrl } from "./envDefaults";

/**
 * 优先 EXPO_PUBLIC_API_BASE_URL（构建时内联）。
 * 未配置时只给本地开发兜底：Android 模拟器走 10.0.2.2，iOS 模拟器走 127.0.0.1。
 * 发布包必须显式注入 HTTPS 地址；不要把模拟器地址带进 staging/prod。
 */
const DEV_DEFAULT = devApiBaseUrl(Platform.OS);

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? DEV_DEFAULT;

// Expo 只会在构建时内联 EXPO_PUBLIC_* 变量；不要用未加前缀的 APP_ENV。
export const APP_ENV = process.env.EXPO_PUBLIC_APP_ENV ?? "development";

const RELEASE_BUILD = process.env.NODE_ENV === "production" || APP_ENV !== "development";
if (RELEASE_BUILD && !API_BASE_URL.startsWith("https://")) {
  // 发布/预发包绝不能把 10.0.2.2 或 http:// 地址带出去；启动时 fail loud。
  throw new Error("EXPO_PUBLIC_API_BASE_URL 必须是 HTTPS（staging/production）");
}
