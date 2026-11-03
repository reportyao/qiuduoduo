import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptLegal, adaptMe } from "@/domain/accountAdapters";
import type { LegalText, MeProfile } from "@/domain/types";
import { useAuthStore } from "@/features/auth/authStore";

export const accountKeys = {
  me: ["me"] as const,
  legal: (region: string) => ["legal", region] as const,
  version: ["app-version"] as const,
};

export function useMeQuery(enabled = true) {
  const ready = useAuthStore((s) => s.ready);
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...accountKeys.me, userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/me"));
      return adaptMe(raw) as MeProfile;
    },
    enabled: enabled && ready,
    staleTime: 20_000,
  });
}

export interface PatchMeInput {
  displayName?: string;
  persona?: "zhuanjia" | "laopao" | "meng";
  oddsFormat?: "decimal" | "hk" | "indo" | "american";
  locale?: "zh" | "en";
}

export function usePatchMeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PatchMeInput) => {
      await callApi(
        api.client.PATCH("/me", {
          body: {
            display_name: input.displayName,
            persona: input.persona,
            odds_format: input.oddsFormat,
            locale: input.locale,
          },
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountKeys.me });
    },
  });
}

export function useDisciplineMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (enabled: boolean) => {
      await callApi(api.client.POST("/me/discipline", { body: { enabled } }));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountKeys.me });
    },
  });
}

export function useRestMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (rested: boolean) => {
      if (rested) {
        await callApi(api.client.POST("/me/rest"));
      } else {
        await callApi(api.client.POST("/me/unrest"));
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountKeys.me });
      void queryClient.invalidateQueries({ queryKey: ["stream"] });
    },
  });
}

export function useMemoryMutations() {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: async (input: { key: string; value: string; confirm?: boolean }) => {
      await callApi(
        api.client.PUT("/me/memories/{key}", {
          params: { path: { key: input.key } },
          body: { value: input.value, source: "你说过", confirm: input.confirm ?? false },
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountKeys.me });
    },
  });
  const remove = useMutation({
    mutationFn: async (key: string) => {
      await callApi(
        api.client.DELETE("/me/memories/{key}", { params: { path: { key } } }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountKeys.me });
    },
  });
  return { save, remove };
}

export function useDeleteAccountMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const raw = await callApi(api.client.DELETE("/me"));
      return raw as { deleted: boolean; cooldown_days: number; message: string };
    },
    onSuccess: () => {
      void queryClient.clear();
    },
  });
}

export function useExportQuery(enabled: boolean) {
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: ["export", userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/me/export"));
      return raw;
    },
    enabled,
    staleTime: 0,
    gcTime: 0,
  });
}

export function useLegalQuery(region = "cn") {
  return useQuery({
    queryKey: accountKeys.legal(region),
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/legal/text", { params: { query: { region } } }),
      );
      return adaptLegal(raw) as LegalText;
    },
    staleTime: 10 * 60_000,
  });
}

export function useAppVersionQuery() {
  return useQuery({
    queryKey: accountKeys.version,
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/app/version"));
      return raw as {
        api: string;
        min_app_version: string;
        force_update_below: string;
        freeze_mode: boolean;
      };
    },
    staleTime: 10 * 60_000,
  });
}

export interface Disclosure {
  privacy: {
    collects: string[];
    not_collects: string[];
    sharing: string;
    storage: string;
  };
  sdk_manifest: { name: string; purpose: string; data: string }[];
  permissions_minimal: Record<string, string>;
  age: string;
}

export function useDisclosureQuery() {
  return useQuery({
    queryKey: ["legal", "disclosure"],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/legal/disclosure"));
      return raw as Disclosure;
    },
    staleTime: 10 * 60_000,
  });
}
