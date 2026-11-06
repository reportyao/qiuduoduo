import { NativeModules, PermissionsAndroid, Platform } from "react-native";

interface JPushNativeModule {
  initialize(): Promise<boolean>;
  getRegistrationId(): Promise<string>;
  isConnected(): Promise<boolean>;
}

function nativeModule(): JPushNativeModule | null {
  if (Platform.OS !== "android") return null;
  return (NativeModules.JPushModule as JPushNativeModule | undefined) ?? null;
}

/** The native module is only present in the Android build; iOS is a no-op for now. */
export async function initializeJPush(): Promise<boolean> {
  const module = nativeModule();
  if (!module) return false;
  try {
    return await module.initialize();
  } catch {
    return false;
  }
}

export async function getJPushRegistrationId(): Promise<string> {
  const module = nativeModule();
  if (!module) return "";
  try {
    return (await module.getRegistrationId()).trim();
  } catch {
    return "";
  }
}

export async function getJPushConnectionState(): Promise<boolean> {
  const module = nativeModule();
  if (!module) return false;
  try {
    return await module.isConnected();
  } catch {
    return false;
  }
}

/** Android 13+ needs the runtime notification permission before anything is visible. */
export async function requestNotificationPermission(): Promise<boolean> {
  if (Platform.OS !== "android" || Number(Platform.Version) < 33) return true;
  try {
    const result = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS,
    );
    return result === PermissionsAndroid.RESULTS.GRANTED;
  } catch {
    return false;
  }
}
