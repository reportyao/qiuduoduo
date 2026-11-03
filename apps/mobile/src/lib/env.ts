export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://10.0.2.2:8100";

// Expo 只会在构建时内联 EXPO_PUBLIC_* 变量；不要用未加前缀的 APP_ENV。
export const APP_ENV = process.env.EXPO_PUBLIC_APP_ENV ?? "development";
