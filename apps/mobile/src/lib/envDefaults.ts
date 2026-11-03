/** 纯函数：不依赖 react-native，便于 Node 单测。 */
export function devApiBaseUrl(platform: string): string {
  return platform === "android" ? "http://10.0.2.2:8100" : "http://127.0.0.1:8100";
}
