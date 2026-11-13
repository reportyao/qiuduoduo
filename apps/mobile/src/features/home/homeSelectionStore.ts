import { create } from "zustand";
import type { OnSaleItem, VerdictSummary } from "@/domain/types";
import type { BriefMatchOption } from "./components/BriefMatchPicker";

export interface PendingHomeSelection {
  option: BriefMatchOption;
  verdict: VerdictSummary | null;
  match: OnSaleItem | null;
  tradeDate: string;
}

interface HomeSelectionState {
  pending: PendingHomeSelection | null;
  request: (selection: PendingHomeSelection) => void;
  consume: () => void;
}

/**
 * 任意 Tab 的「今日比赛」浮层选中后，把同一套对话交互交给首页消费。
 * 首页负责切日期、聚焦比赛并追加「看这场」消息，避免两套交互分叉。
 */
export const useHomeSelectionStore = create<HomeSelectionState>((set) => ({
  pending: null,
  request: (selection) => set({ pending: selection }),
  consume: () => set({ pending: null }),
}));
