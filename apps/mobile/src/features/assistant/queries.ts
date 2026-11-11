import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptChat } from "@/domain/accountAdapters";
import type { ChatCard } from "@/domain/types";
import { usePersonaContent } from "@/features/personas/usePersona";

// 进程内匿名会话：只用于 LLM 私有缓存隔离，不落盘、不含设备标识。
const CHAT_SESSION = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

export function useChatMutation() {
  const queryClient = useQueryClient();
  const { id: persona } = usePersonaContent();
  return useMutation({
    mutationFn: async (input: { text: string; matchId?: string }): Promise<ChatCard> => {
      const raw = await callApi(api.client.POST("/chat", {
        body: {
          text: input.text,
          session_id: CHAT_SESSION,
          match_id: input.matchId ?? "",
          persona,
        },
      }));
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
