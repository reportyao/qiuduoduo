import { useMutation } from "@tanstack/react-query";
import type { components } from "@jieqiu/api-client";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";

export type ParlayCheck = components["schemas"]["ParlayCheckResponse"];
export type ParlayLegInput = components["schemas"]["ParlayLegIn"];
export type ParlayNote = components["schemas"]["ParlayNote"];
export type ParlayPlan = components["schemas"]["ParlayPlanResponse"];
export type ParlayPlanItem = components["schemas"]["ParlayPlanItem"];

export interface ParlayCheckInput {
  legs: ParlayLegInput[];
  stake: number;
}

export function useParlayCheckMutation() {
  return useMutation({
    mutationFn: async (input: ParlayCheckInput): Promise<ParlayCheck> =>
      callApi(api.client.POST("/tools/parlay/check", { body: input })),
  });
}

export function useParlayPlanMutation() {
  return useMutation({
    mutationFn: async (input: { stake: number; date?: string }): Promise<ParlayPlan> =>
      callApi(api.client.POST("/tools/parlay/plan", { body: input })),
  });
}
