import { Platform } from "react-native";
import * as FileSystem from "expo-file-system";
import { usePrefsStore } from "@/features/preferences/prefsStore";
import { useComplianceStore } from "@/features/compliance/complianceStore";

/** 账号级本机状态在退出/注销时统一清理，避免下一位使用者看到上一位的数据。 */
export async function resetLocalAccountState(): Promise<void> {
  const prefs = usePrefsStore.getState();
  const avatarUri = prefs.avatarUri;
  prefs.setPersona("zhuanjia");
  prefs.setOddsFormat("decimal");
  prefs.setAvatarUri(null);
  useComplianceStore.getState().clearPgsi();
  if (Platform.OS !== "web" && avatarUri && FileSystem.documentDirectory) {
    const dir = `${FileSystem.documentDirectory}avatars/`;
    if (avatarUri.startsWith(dir)) {
      await FileSystem.deleteAsync(avatarUri, { idempotent: true }).catch(() => {});
    }
  }
}
