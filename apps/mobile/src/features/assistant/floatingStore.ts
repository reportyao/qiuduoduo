import { create } from "zustand";

interface FloatingState {
  /** 首页滚动阅读时收起，避免浮层压住正文。 */
  compact: boolean;
  setCompact: (compact: boolean) => void;
  /** 打开的底部弹层数量；>0 时隐藏悬浮头像，防止盖住遮罩与弹层内容。 */
  sheetDepth: number;
  pushSheet: () => void;
  popSheet: () => void;
  /** 跨 Tab 共用的「今日比赛」弹层。 */
  pickerOpen: boolean;
  openPicker: () => void;
  closePicker: () => void;
}

export const useFloatingStore = create<FloatingState>((set) => ({
  compact: false,
  setCompact: (compact) => set({ compact }),
  sheetDepth: 0,
  pushSheet: () => set((state) => ({ sheetDepth: state.sheetDepth + 1 })),
  popSheet: () => set((state) => ({ sheetDepth: Math.max(0, state.sheetDepth - 1) })),
  pickerOpen: false,
  openPicker: () => set({ pickerOpen: true }),
  closePicker: () => set({ pickerOpen: false }),
}));
