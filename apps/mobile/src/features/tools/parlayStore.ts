import { create } from "zustand";

export type ParlayDir = "home" | "draw" | "away";

export interface ParlayLeg {
  verdictId: string;
  matchId: string;
  tradeDate: string;
  home: string;
  away: string;
  kickoff: string;
  dir: ParlayDir;
  odds: number;
  rake: number | null;
  /** 非已发布/无模型覆盖：整组会标“未复核·仅市场参考”。 */
  marketOnly: boolean;
}

export const PARLAY_MAX_LEGS = 6;

interface ParlayState {
  legs: ParlayLeg[];
  add: (leg: ParlayLeg) => { ok: boolean; reason?: string };
  remove: (verdictId: string) => void;
  clear: () => void;
}

/** 详情页“加入串关”与串关页共享的腿池；最多 6 腿。 */
export const useParlayStore = create<ParlayState>((set, get) => ({
  legs: [],
  add: (leg) => {
    const legs = get().legs;
    if (legs.some((item) => item.verdictId === leg.verdictId)) {
      return { ok: false, reason: "这场已经在串关里了" };
    }
    if (legs.length >= PARLAY_MAX_LEGS) {
      return { ok: false, reason: `串关最多 ${PARLAY_MAX_LEGS} 场，腿越多相关性和成本越高` };
    }
    set({ legs: [...legs, leg] });
    return { ok: true };
  },
  remove: (verdictId) => set({ legs: get().legs.filter((item) => item.verdictId !== verdictId) }),
  clear: () => set({ legs: [] }),
}));
