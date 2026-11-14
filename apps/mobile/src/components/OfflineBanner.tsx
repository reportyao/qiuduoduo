import { useEffect, useRef } from "react";
import { StyleSheet, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useOfflineStore } from "@/lib/offlineStore";
import { colors, radii, spacing } from "@/theme/tokens";
import { Text } from "@/components/ui";

/**
 * 全局离线横幅：断网时吸顶提示，恢复后自动消失并触发一次全量重取。
 * 放在 Stack 之上（absolute 覆盖），不参与页面布局。
 */
export function OfflineBanner() {
  const queryClient = useQueryClient();
  const insets = useSafeAreaInsets();
  const isOnline = useOfflineStore((s) => s.isOnline);
  const reconnectCount = useOfflineStore((s) => s.reconnectCount);
  const lastHandled = useRef(0);

  // 恢复联网：补拉一次全部查询 + 续跑离线期间被暂停的 mutation。
  useEffect(() => {
    if (isOnline !== true || reconnectCount === 0 || reconnectCount === lastHandled.current) return;
    lastHandled.current = reconnectCount;
    void queryClient.invalidateQueries();
    void queryClient.resumePausedMutations();
  }, [isOnline, queryClient, reconnectCount]);

  if (isOnline !== false) return null;

  return (
    <View
      pointerEvents="none"
      accessibilityLiveRegion="polite"
      accessibilityRole="alert"
      style={[styles.banner, { top: insets.top + 4 }]}
    >
      <Text variant="captionStrong" style={styles.text}>
        网络已断开，正在显示缓存数据
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    backgroundColor: colors.toastWarningBg,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    shadowColor: "#102018",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 12,
    elevation: 6,
  },
  text: { color: colors.amberAccent },
});
