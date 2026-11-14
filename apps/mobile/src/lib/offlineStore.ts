import { create } from "zustand";
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
  // isInternetReachable 为 null（探测中）时按可达处理，避免误报离线。
  const online = Boolean(state.isConnected) && state.isInternetReachable !== false;
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
