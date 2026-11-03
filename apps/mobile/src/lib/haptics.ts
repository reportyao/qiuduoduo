import * as Haptics from "expo-haptics";

export type FeedbackKind = "light" | "medium" | "success" | "warning" | "error";

/**
 * 所有触觉反馈从这里走：页面不直接调用 Haptics，方便统一降级与测试。
 * Web/不支持触觉的设备静默失败，不影响主流程。
 */
export function haptic(kind: FeedbackKind = "light"): void {
  const run = async () => {
    switch (kind) {
      case "success":
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        break;
      case "warning":
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        break;
      case "error":
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        break;
      case "medium":
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        break;
      default:
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  };
  void run().catch(() => {});
}
