import { create } from "zustand";
import { onlineManager } from "@tanstack/react-query";
import { Platform } from "react-native";
import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";

/**
 * 全局离线状态：NetInfo 订阅写入 store，UI（离线横幅）与 QueryClient（恢复重取）共用。
 * 初始值 unknown，首次回调后才有确定值，避免把「还没探测」当成「离线」。
 */
interface OfflineState {
  /** null = 尚未完成首次探测。 */
  isOnline: boolean | null;
  /** 上一次在线→离线→在线 的次数，恢复联网时自增作为重取信号。 */
  reconnectCount: number;
}

export const useOfflineStore = create<OfflineState>(() => ({
  isOnline: null,
  reconnectCount: 0,
}));

let unsubscribed = false;

function handle(state: NetInfoState) {
  // web 端只用 isConnected（navigator.onLine）：部分浏览器/WebView 的
  // Network Information API 会把 rtt/downlink 报成 0，isInternetReachable 被误判为
  // false → 全页误挂「网络已断开」横幅（2026-11-14 H5 线上复现）。
  // 原生端保留 isInternetReachable 校验（null 探测中按可达处理，避免误报）。
  const online = Platform.OS === "web"
    ? Boolean(state.isConnected)
    : Boolean(state.isConnected) && state.isInternetReachable !== false;
  // TanStack 默认 onlineManager 在 RN 上拿不到真实网络状态（navigator.onLine 恒 true），
  // 用 NetInfo 驱动它：离线时 mutation 走正常的 pause 语义，恢复时自动续跑。
  onlineManager.setOnline(online);
  const prev = useOfflineStore.getState().isOnline;
  useOfflineStore.setState((s) => ({
    isOnline: online,
    reconnectCount: prev === false && online ? s.reconnectCount + 1 : s.reconnectCount,
  }));
}

/** 在根布局调用一次；返回退订函数。 */
export function startNetworkListener(): () => void {
  if (unsubscribed) return () => {};
  unsubscribed = true;
  void NetInfo.fetch().then(handle);
  const unsubscribe = NetInfo.addEventListener(handle);
  return () => {
    unsubscribe();
    unsubscribed = false;
  };
}
