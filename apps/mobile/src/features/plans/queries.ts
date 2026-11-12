import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/features/auth/authStore";
import { callApi } from "@/lib/callApi";

export type PlanRisk = "stable" | "balanced" | "aggressive";

export interface PlanLeg {
  verdict_id: string;
  match_id: string;
  match_no: string;
  league: string;
  home: string;
  away: string;
  market: string;
  line: string;
  direction: string;
  odds: number;
  allocation: number;
  model_prob: number | null;
  market_prob: number | null;
  edge: number | null;
  quality_score: number | null;
  selection_reason: string;
  result: string;
}

export interface PlanBet {
  id: string;
  bet_type: "single" | "parlay";
  label: string;
  stake: number;
  odds: number;
  status: string;
  pnl: number;
  legs: PlanLeg[];
}

export interface PlanCycle {
  id: string;
  name: string;
  risk_level: PlanRisk;
  cycle_no: number;
  start_at: string;
  end_at: string;
  budget: number;
  target_matches: number;
  status: string;
  total_stake: number;
  total_return: number;
  pnl: number;
  roi: number | null;
  max_drawdown: number | null;
  published_at: string | null;
  bet_count: number;
  match_count: number;
  bets: PlanBet[];
}

export interface PlanSummaryItem {
  name: string;
  cycles: number;
  settled: number;
  pnl: number;
  roi: number;
  last_7d: number;
  last_30d: number;
}

export interface PlanCurrentResponse {
  tier: "free" | "pro" | "max";
  locked: boolean;
  plan: PlanCycle | null;
}

export function usePlanSummaryQuery() {
  return useQuery({
    queryKey: ["plans", "summary"],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/plans/summary"));
      return (raw as unknown as { plans: Record<PlanRisk, PlanSummaryItem> }).plans;
    },
    staleTime: 60_000,
  });
}

export function usePlanCurrentQuery(risk: PlanRisk) {
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  const ready = useAuthStore((s) => s.ready);
  return useQuery({
    queryKey: ["plans", "current", risk, userId],
    enabled: ready,
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/plans/current", {
        params: { query: { risk } },
      }));
      return raw as unknown as PlanCurrentResponse;
    },
    staleTime: 30_000,
  });
}

export function usePlanHistoryQuery(risk: PlanRisk) {
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  const ready = useAuthStore((s) => s.ready);
  return useQuery({
    queryKey: ["plans", "history", risk, userId],
    enabled: ready,
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/plans/history", {
        params: { query: { risk, limit: 30 } },
      }));
      return raw as unknown as {
        tier: "free" | "pro" | "max";
        locked: boolean;
        items: PlanCycle[];
      };
    },
    staleTime: 60_000,
  });
}

export function useMembershipQuery() {
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  const ready = useAuthStore((s) => s.ready);
  return useQuery({
    queryKey: ["membership", "me", userId],
    enabled: ready,
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/membership/me"));
      return raw as unknown as {
        tier: "free" | "pro" | "max";
        status: string;
        expires_at: string | null;
        source: string;
        is_paid: boolean;
        quota?: { limit: number | null; used: number; remaining: number | null };
      };
    },
    staleTime: 60_000,
  });
}

export function usePlanCycleQuery(cycleId: string) {
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  const ready = useAuthStore((s) => s.ready);
  return useQuery({
    queryKey: ["plans", "cycle", cycleId, userId],
    enabled: Boolean(cycleId) && ready,
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/plans/cycles/{cycle_id}", {
        params: { path: { cycle_id: cycleId } },
      }));
      return raw as unknown as PlanCurrentResponse;
    },
    staleTime: 30_000,
  });
}
