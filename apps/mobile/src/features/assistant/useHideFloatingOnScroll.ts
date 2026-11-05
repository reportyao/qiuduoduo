import { useCallback, useRef } from "react";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";
import { useFocusEffect } from "expo-router";
import { useFloatingStore } from "./floatingStore";

/**
 * 任一 Tab 开始纵向阅读时收起悬浮头像。
 * 头像固定在屏幕顶部，不随内容滚动；页面滚过 96px 后继续显示会压住正文。
 */
export function useHideFloatingOnScroll(threshold = 96) {
  const setCompact = useFloatingStore((s) => s.setCompact);
  const y = useRef(0);

  useFocusEffect(
    useCallback(() => {
      setCompact(y.current > threshold);
      return () => setCompact(false);
    }, [setCompact, threshold]),
  );

  return useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const next = event.nativeEvent.contentOffset.y;
      const wasHidden = y.current > threshold;
      const nowHidden = next > threshold;
      y.current = next;
      if (wasHidden !== nowHidden) setCompact(nowHidden);
    },
    [setCompact, threshold],
  );
}
