import { create } from "zustand";

interface FloatingState {
  /** 首页滚动阅读时缩小，但始终可见、可点击。 */
  compact: boolean;
  setCompact: (compact: boolean) => void;
  /** 跨 Tab 共用的「今日比赛」弹层。 */
  pickerOpen: boolean;
  openPicker: () => void;
  closePicker: () => void;
}

export const useFloatingStore = create<FloatingState>((set) => ({
  compact: false,
  setCompact: (compact) => set({ compact }),
  pickerOpen: false,
  openPicker: () => set({ pickerOpen: true }),
  closePicker: () => set({ pickerOpen: false }),
}));
