import { useEffect, useState } from "react";
import { AppState } from "react-native";

/** 共享时钟：倒计时/相对时间/自排除到期都要随时间重算，不能只在渲染那一刻算一次。 */
export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") setNow(Date.now());
    });
    return () => {
      clearInterval(timer);
      sub.remove();
    };
  }, [intervalMs]);
  return now;
}
