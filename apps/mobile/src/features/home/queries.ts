import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptOnSale, adaptStream } from "@/domain/streamAdapters";
import { adaptRecommendationToday } from "@/domain/recommendationAdapters";
import { adaptFocus, adaptPulse } from "@/domain/focusAdapters";
import type { StreamResponse } from "@/domain/types";
import { useAuthStore } from "@/features/auth/authStore";

export const streamKeys = {
  all: ["stream"] as const,
  date: (date: string, userId: string) => ["stream", date, userId] as const,
};

/** 判决流：游标分页，第一页即首屏；后续页只在用户上拉时请求。 */
export function useStreamQuery(date: string, enabled = true) {
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useInfiniteQuery({
    // stream 带 you 块（连败/休息），必须按用户隔离，不能把上一个账号的 you 闪给下一个。
    queryKey: streamKeys.date(date, userId),
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const raw = await callApi(
        api.client.GET("/stream", {
          params: { query: { date, limit: 50, cursor: pageParam ?? undefined } },
        }),
      );
      return adaptStream(raw);
    },
    getNextPageParam: (last) => last.nextCursor,
    enabled,
    staleTime: 15_000,
    refetchInterval: 60_000,
  });
}

export function flattenStream(pages: StreamResponse[]): {
  page: StreamResponse;
  verdicts: StreamResponse["verdicts"];
} {
  const first = pages[0];
  const verdicts = pages.flatMap((page) => page.verdicts);
  return { page: first, verdicts };
}

export function useOnSaleQuery(enabled = true) {
  return useQuery({
    queryKey: ["on-sale"],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/matches/on-sale"));
      return adaptOnSale(raw);
    },
    enabled,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}


/** 已发布的推荐快照；旧后端 404 时静默回退到 stream。 */
export function useRecommendationsTodayQuery(date: string, enabled = true) {
  return useQuery({
    queryKey: ["recommendations-today", date],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/recommendations/today", {
        params: { query: { date } },
      }));
      return adaptRecommendationToday(raw);
    },
    enabled,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}


/** 单场聚焦：结论/覆盖率/情报/capabilities 的服务端事实源。 */
export function useFocusQuery(matchId: string | null, date: string, enabled = true) {
  return useQuery({
    queryKey: ["match-focus", matchId, date],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/matches/{match_id}/focus", {
        params: { path: { match_id: matchId as string }, query: { date } },
      }));
      return adaptFocus(raw);
    },
    enabled: enabled && Boolean(matchId),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

/** 公开数据脉搏：真实计数 + 源新鲜度，不乘前端系数。 */
export function usePulseQuery(date: string, enabled = true) {
  return useQuery({
    queryKey: ["pulse", date],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/stats/pulse", {
        params: { query: { date } },
      }));
      return adaptPulse(raw);
    },
    enabled,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
