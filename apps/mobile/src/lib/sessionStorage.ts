import { Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

/**
 * 会话存储：Android/iOS 优先 SecureStore；Web（以及 SecureStore 不可用的设备）
 * 回落 AsyncStorage。这样 Web 预览不会每次刷新都变成新设备，原生仍走加密存储。
 */
export async function readSessionRaw(key: string): Promise<string | null> {
  if (Platform.OS !== "web") {
    // 原生端不再回落到明文 AsyncStorage：SecureStore 失败时宁可让用户重新登录，
    // 也不让旧账号从旧副本里“复活”。删除失败会由 writeSessionRaw 写墓碑。
    try {
      const tomb = await AsyncStorage.getItem(`${key}.tombstone`);
      if (tomb === "1") return null;
      return await SecureStore.getItemAsync(key);
    } catch {
      return null;
    }
  }
  return AsyncStorage.getItem(key);
}

export async function writeSessionRaw(key: string, value: string | null): Promise<void> {
  if (Platform.OS !== "web") {
    if (value == null) {
      try {
        await SecureStore.deleteItemAsync(key);
        await AsyncStorage.removeItem(`${key}.tombstone`);
        await AsyncStorage.removeItem(key);
        return;
      } catch (error) {
        // 删除失败：写墓碑，保证下次启动不会读回旧 SecureStore 值。
        try {
          await AsyncStorage.setItem(`${key}.tombstone`, "1");
        } catch {
          // 连墓碑都写不了；readSessionRaw 会因 SecureStore 错误返回 null。
        }
        throw error;
      }
    }
    await SecureStore.setItemAsync(key, value);
    await AsyncStorage.removeItem(`${key}.tombstone`);
    await AsyncStorage.removeItem(key);
    return;
  }
  await AsyncStorage.removeItem(`${key}.tombstone`);
  if (value == null) {
    await AsyncStorage.removeItem(key);
  } else {
    await AsyncStorage.setItem(key, value);
  }
}
