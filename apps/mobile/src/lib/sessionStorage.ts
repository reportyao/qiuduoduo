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
      const value = await SecureStore.getItemAsync(key);
      if (value != null) return value;
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
