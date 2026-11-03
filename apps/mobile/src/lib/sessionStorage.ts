import { Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

/**
 * 会话存储：Android/iOS 优先 SecureStore；Web（以及 SecureStore 不可用的设备）
 * 回落 AsyncStorage。这样 Web 预览不会每次刷新都变成新设备，原生仍走加密存储。
 */
export async function readSessionRaw(key: string): Promise<string | null> {
  if (Platform.OS !== "web") {
    try {
      // 成功读到 null 就是「没有会话」；只有 SecureStore 抛错才回落，
      // 否则旧的 AsyncStorage 副本会在登出后把账号“复活”。
      return await SecureStore.getItemAsync(key);
    } catch {
      // 继续回落
    }
  }
  return AsyncStorage.getItem(key);
}

export async function writeSessionRaw(key: string, value: string | null): Promise<void> {
  if (Platform.OS !== "web") {
    try {
      if (value == null) {
        await SecureStore.deleteItemAsync(key);
      } else {
        await SecureStore.setItemAsync(key, value);
      }
      // 清理可能存在的旧 AsyncStorage 副本，避免双写不一致。
      await AsyncStorage.removeItem(key);
      return;
    } catch {
      // 继续回落
    }
  }
  if (value == null) {
    await AsyncStorage.removeItem(key);
  } else {
    await AsyncStorage.setItem(key, value);
  }
}
