import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptBets, adaptLedger, adaptPostmortem, adaptWeekly } from "@/domain/accountAdapters";
import type { BetRecord, LedgerResponse, Postmortem, WeeklyReport } from "@/domain/types";
import { useAuthStore } from "@/features/auth/authStore";

export const recordKeys = {
  bets: ["bets"] as const,
  weekly: ["weekly"] as const,
  ledger: ["ledger"] as const,
  betPostmortem: (id: number) => ["bets", id, "postmortem"] as const,
};

export function useBetsQuery(enabled = true) {
  const ready = useAuthStore((s) => s.ready);
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...recordKeys.bets, userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/bets"));
      return adaptBets(raw) as BetRecord[];
    },
    enabled: enabled && ready,
    staleTime: 15_000,
  });
}

export interface CreateBetInput {
  verdictId: string;
  amount: number;
  confirm?: boolean;
}

export interface CreatedBet {
  id: number;
  verdictId: string;
  amount: number;
  pickDir: string;
  streak: Record<string, unknown>;
}

export function useCreateBetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateBetInput): Promise<CreatedBet> => {
      const raw = await callApi(
        api.client.POST("/bets", {
          body: {
            verdict_id: input.verdictId,
            amount: input.amount,
            confirm: input.confirm ?? false,
          },
        }),
      );
      return raw as CreatedBet;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: recordKeys.bets });
      void queryClient.invalidateQueries({ queryKey: recordKeys.weekly });
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useDeleteBetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (betId: number) => {
      await callApi(
        api.client.DELETE("/bets/{bet_id}", { params: { path: { bet_id: betId } } }),
      );
      return betId;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: recordKeys.bets });
      void queryClient.invalidateQueries({ queryKey: recordKeys.weekly });
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useBetPostmortemQuery(betId: number | undefined) {
  return useQuery({
    queryKey: recordKeys.betPostmortem(betId ?? 0),
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/bets/{bet_id}/postmortem", {
          params: { path: { bet_id: betId! } },
        }),
      );
      return adaptPostmortem(raw) as Postmortem;
    },
    enabled: Boolean(betId),
  });
}

export function useWeeklyQuery(enabled = true) {
  const ready = useAuthStore((s) => s.ready);
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...recordKeys.weekly, userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/weekly-report"));
      return adaptWeekly(raw) as WeeklyReport;
    },
    enabled: enabled && ready,
    staleTime: 30_000,
  });
}

export function useLedgerQuery() {
  return useQuery({
    queryKey: recordKeys.ledger,
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/api/ledger"));
      return adaptLedger(raw) as LedgerResponse;
    },
    staleTime: 30_000,
  });
}
