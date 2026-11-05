import { create } from "zustand";
import type { GateKey, GateResult, OnSaleItem, VerdictDetail, VerdictSummary } from "@/domain/types";

export interface FocusTarget {
  matchId: string;
  tradeDate: string;
  verdictId: string | null;
  matchNo: string;
  league: string;
  home: string;
  away: string;
  kickoff: string;
  saleClose: string;
  status: string;
  gates: Partial<Record<GateKey, GateResult>> | null;
  rake: number | null;
  source: "verdict" | "onsale" | "detail";
}

function base(source: FocusTarget["source"], value: {
  matchId: string;
  tradeDate: string;
  verdictId: string | null;
  matchNo: string;
  league: string;
  home: string;
  away: string;
  kickoff: string;
  saleClose: string;
  status: string;
  gates: Partial<Record<GateKey, GateResult>> | null;
  rake: number | null;
}): FocusTarget {
  return { ...value, source };
}

export function focusFromVerdict(verdict: VerdictSummary, tradeDate: string): FocusTarget {
  return base("verdict", {
    matchId: verdict.matchId,
    tradeDate,
    verdictId: verdict.id,
    matchNo: verdict.matchNo,
    league: verdict.league,
    home: verdict.home,
    away: verdict.away,
    kickoff: verdict.kickoff,
    saleClose: verdict.kickoff,
    status: verdict.status,
    gates: verdict.gates,
    rake: verdict.rake,
  });
}

export function focusFromOnSale(match: OnSaleItem, tradeDate: string): FocusTarget {
  return base("onsale", {
    matchId: match.matchId,
    tradeDate,
    verdictId: match.verdictId,
    matchNo: match.matchNo,
    league: match.league,
    home: match.home,
    away: match.away,
    kickoff: match.kickoff,
    saleClose: match.saleClose,
    status: match.status ?? "onsale",
    gates: match.gates,
    rake: match.rake,
  });
}

export function focusFromDetail(detail: VerdictDetail): FocusTarget {
  return base("detail", {
    matchId: detail.matchId,
    tradeDate: detail.tradeDate,
    verdictId: detail.id,
    matchNo: detail.matchNo,
    league: detail.league,
    home: detail.home,
    away: detail.away,
    kickoff: detail.kickoff,
    saleClose: detail.kickoff,
    status: detail.status,
    gates: detail.gates,
    rake: detail.rake,
  });
}

interface FocusState {
  focus: FocusTarget | null;
  setFocus: (focus: FocusTarget) => void;
  clearFocus: () => void;
}

/** 首页聚焦：不是后端 status，而是当前正在对话的那一场。 */
export const useFocusStore = create<FocusState>((set) => ({
  focus: null,
  setFocus: (focus) => set({ focus }),
  clearFocus: () => set({ focus: null }),
}));
