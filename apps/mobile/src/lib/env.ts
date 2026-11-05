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
// 仅内部测试包可显式放开 HTTP；正式发布不设置这个变量，仍然 fail loud。
const ALLOW_HTTP = process.env.EXPO_PUBLIC_ALLOW_HTTP === "true";
if (RELEASE_BUILD && !API_BASE_URL.startsWith("https://") && !ALLOW_HTTP) {
  throw new Error("EXPO_PUBLIC_API_BASE_URL 必须是 HTTPS（staging/production）");
}
