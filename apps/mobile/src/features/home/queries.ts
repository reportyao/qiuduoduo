import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptOnSale, adaptStream } from "@/domain/streamAdapters";
import type { StreamResponse } from "@/domain/types";
import { useAuthStore } from "@/features/auth/authStore";

export const streamKeys = {
  all: ["stream"] as const,
  date: (date: string, userId: string) => ["stream", date, userId] as const,
};

/** 判决流：游标分页，第一页即首屏；后续页只在用户上拉时请求。 */
export function useStreamQuery(date: string) {
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
