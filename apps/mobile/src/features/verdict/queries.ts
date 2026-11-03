import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import {
  adaptSeal,
  adaptVerdictDetail,
  adaptWhyNot,
} from "@/domain/streamAdapters";
import { adaptPostmortem } from "@/domain/accountAdapters";
import type { Postmortem, SealResponse, VerdictDetail, WhyNotResponse } from "@/domain/types";

export const verdictKeys = {
  detail: (id: string) => ["verdict", id] as const,
  seal: (id: string) => ["verdict", id, "seal"] as const,
  whyNot: (matchId: string, date: string) => ["why-not", matchId, date] as const,
  postmortem: (id: string) => ["postmortem", id] as const,
};

export function useVerdictDetailQuery(id: string | undefined) {
  return useQuery({
    queryKey: verdictKeys.detail(id ?? ""),
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/verdicts/{verdict_id}", { params: { path: { verdict_id: id! } } }),
      );
      const detail = adaptVerdictDetail(raw);
      if (!detail) throw new Error("判决数据不完整");
      return detail as VerdictDetail;
    },
    enabled: Boolean(id),
    staleTime: 60_000,
  });
}

export function useSealQuery(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: verdictKeys.seal(id ?? ""),
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/verdicts/{verdict_id}/seal", {
          params: { path: { verdict_id: id! } },
        }),
      );
      return adaptSeal(raw) as SealResponse;
    },
    enabled: Boolean(id) && enabled,
    staleTime: 5 * 60_000,
  });
}

export function useWhyNotQuery(matchId: string | undefined, date: string, enabled = true) {
  return useQuery({
    queryKey: verdictKeys.whyNot(matchId ?? "", date),
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/matches/{match_id}/why-not", {
          params: { path: { match_id: matchId! }, query: { date } },
        }),
      );
      return adaptWhyNot(raw) as WhyNotResponse;
    },
    enabled: Boolean(matchId) && enabled,
    retry: false,
  });
}

export function useVerdictPostmortemQuery(id: string | undefined) {
  return useQuery({
    queryKey: verdictKeys.postmortem(id ?? ""),
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/verdicts/{verdict_id}/postmortem", {
          params: { path: { verdict_id: id! } },
        }),
      );
      return adaptPostmortem(raw) as Postmortem;
    },
    enabled: Boolean(id),
  });
}

/** 关注比赛：POST/GET/DELETE /me/watch。首页/详情共用。 */
export function useWatchMatchMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { targetId: string; watching: boolean; watchId?: number }) => {
      if (input.watching && input.watchId) {
        await callApi(
          api.client.DELETE("/me/watch/{watch_id}", {
            params: { path: { watch_id: input.watchId } },
          }),
        );
        return { watching: false };
      }
      await callApi(
        api.client.POST("/me/watch", {
          body: { target_type: "match", target_id: input.targetId, events: [] },
        }),
      );
      return { watching: true };
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["watch"] });
    },
  });
}
