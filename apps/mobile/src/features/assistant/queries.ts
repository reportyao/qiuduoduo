import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptChat } from "@/domain/accountAdapters";
import type { ChatCard } from "@/domain/types";

export function useChatMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string): Promise<ChatCard> => {
      const raw = await callApi(api.client.POST("/chat", { body: { text } }));
      return adaptChat(raw);
    },
    onSuccess: (card) => {
      if (card.type === "memory_write" || card.type === "memory_query") {
        void queryClient.invalidateQueries({ queryKey: ["me"] });
      }
    },
  });
}

export function useShareVerdictMutation() {
  return useMutation({
    mutationFn: async (input: { verdictId: string; persona: string }) => {
      const raw = await callApi(
        api.client.POST("/share/verdict/{verdict_id}", {
          params: {
            path: { verdict_id: input.verdictId },
            query: { persona: input.persona },
          },
        }),
      );
      return raw as { share_id: string; text: string; url: string; deep_link: string };
    },
  });
}
