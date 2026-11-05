import { Redirect } from "expo-router";

/** 兼容服务端与历史分享里的 jieqiu://today 深链。 */
export default function TodayRedirect() {
  return <Redirect href="/(tabs)" />;
}
