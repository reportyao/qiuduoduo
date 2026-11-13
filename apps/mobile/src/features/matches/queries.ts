import { useQuery } from "@tanstack/react-query";
import type { components } from "@jieqiu/api-client";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";

export type LiveBoard = components["schemas"]["LiveBoardResponse"];
export type LiveMatch = components["schemas"]["LiveMatch"];
export type ResultBoard = components["schemas"]["ResultBoardResponse"];
export type ResultMatch = components["schemas"]["ResultMatch"];
export type PredictionHistory = components["schemas"]["PredictionHistoryResponse"];
export type PredictionHistoryMatch = components["schemas"]["PredictionHistoryMatch"];
export type PredictionHistoryDetail =
  components["schemas"]["PredictionHistoryDetailResponse"];
export type PredictionItem = components["schemas"]["PredictionSettlementItem"];
export type PredictionAccuracy = components["schemas"]["PredictionAccuracy"];

export const matchKeys = {
  live: ["matches", "live"] as const,
  results: (date: string) => ["matches", "results", date] as const,
  history: (date: string) => ["matches", "predictions", date] as const,
  historyDetail: (matchId: string) => ["matches", "predictions", "detail", matchId] as const,
};

/** 即时：进行中且已映射竞彩的场次；30 秒轮询，页面不展示预测。 */
export function useLiveBoardQuery(enabled = true) {
  return useQuery({
    queryKey: matchKeys.live,
    queryFn: async () => callApi(api.client.GET("/matches/live")),
    enabled,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

/** 赛果：指定自然日；只含比分与状态。 */
export function useResultBoardQuery(date: string, enabled = true) {
  return useQuery({
    queryKey: matchKeys.results(date),
    queryFn: async () =>
      callApi(api.client.GET("/matches/results", { params: { query: { date } } })),
    enabled,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
}

/** 预测战绩：当日全部已结算维度汇总 + 每场主预测。 */
export function usePredictionHistoryQuery(date: string, enabled = true) {
  return useQuery({
    queryKey: matchKeys.history(date),
    queryFn: async () =>
      callApi(api.client.GET("/predictions/history", { params: { query: { date } } })),
    enabled,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
}

/** 单场 25 维预测 vs 实际。 */
export function usePredictionDetailQuery(matchId: string, enabled = true) {
  return useQuery({
    queryKey: matchKeys.historyDetail(matchId),
    queryFn: async () =>
      callApi(
        api.client.GET("/predictions/history/{match_id}", {
          params: { path: { match_id: matchId } },
        }),
      ),
    enabled: enabled && Boolean(matchId),
    retry: false,
    staleTime: 120_000,
  });
}
