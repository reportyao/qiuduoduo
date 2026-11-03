import { Redirect } from "expo-router";
import { usePrefsStore } from "@/features/preferences/prefsStore";

/**
 * 入口只做分流；真正的守卫在根布局，防止深链绕过。
 * 必须等偏好水合完成再判断，否则冷启动会先读到默认 unknown，
 * 把已同意年龄门的用户错误重定向到 onboarding。
 */
export default function Index() {
  const hydrated = usePrefsStore((s) => s.hydrated);
  const ageDecision = usePrefsStore((s) => s.ageDecision);
  if (!hydrated) return null;
  if (ageDecision === "unknown") return <Redirect href="/onboarding" />;
  if (ageDecision === "minor") return <Redirect href="/minor" />;
  return <Redirect href="/(tabs)" />;
}
