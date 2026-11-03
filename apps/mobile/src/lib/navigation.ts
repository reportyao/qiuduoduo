import type { useRouter } from "expo-router";

type Router = ReturnType<typeof useRouter>;

/** 深链冷启动时导航栈没有历史，router.back() 会变成死按钮；统一回首页。 */
export function goBackOr(router: Router, fallback: "/(tabs)" = "/(tabs)"): void {
  if (router.canGoBack()) {
    router.back();
  } else {
    router.replace(fallback);
  }
}
