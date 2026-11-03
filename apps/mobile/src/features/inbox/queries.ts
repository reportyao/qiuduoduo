import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { adaptInbox, adaptNotify, adaptWatch } from "@/domain/accountAdapters";
import { useAuthStore } from "@/features/auth/authStore";
import type { InboxResponse, NotifySettings, WatchItem } from "@/domain/types";

export const inboxKeys = {
  list: ["inbox"] as const,
  unread: ["inbox", "unread"] as const,
  watch: ["watch"] as const,
  notify: ["notify-settings"] as const,
};

export function useInboxQuery(unreadOnly = false) {
  const ready = useAuthStore((s) => s.ready);
  const hasSession = useAuthStore((s) => Boolean(s.session));
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...inboxKeys.list, userId, unreadOnly],
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/me/inbox", {
          params: { query: { unread: unreadOnly, limit: 50 } },
        }),
      );
      return adaptInbox(raw) as InboxResponse;
    },
    staleTime: 15_000,
    enabled: ready && hasSession,
  });
}

export function useUnreadCountQuery() {
  const ready = useAuthStore((s) => s.ready);
  const hasSession = useAuthStore((s) => Boolean(s.session));
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...inboxKeys.unread, userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/me/inbox/unread-count"));
      return raw as { unread: number };
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
    enabled: ready && hasSession,
  });
}

export function useInboxMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: inboxKeys.list });
    void queryClient.invalidateQueries({ queryKey: inboxKeys.unread });
  };
  const markRead = useMutation({
    mutationFn: async (id: number) => {
      await callApi(
        api.client.POST("/me/inbox/{notification_id}/read", {
          params: { path: { notification_id: id } },
        }),
      );
    },
    onSuccess: invalidate,
  });
  const readAll = useMutation({
    mutationFn: async () => {
      await callApi(api.client.POST("/me/inbox/read-all"));
    },
    onSuccess: invalidate,
  });
  const click = useMutation({
    mutationFn: async (id: number) => {
      const raw = await callApi(
        api.client.POST("/me/inbox/{notification_id}/click", {
          params: { path: { notification_id: id } },
        }),
      );
      return raw as { ok: boolean; deeplink: string | null };
    },
    onSuccess: invalidate,
  });
  return { markRead, readAll, click };
}

export function useWatchQuery() {
  const ready = useAuthStore((s) => s.ready);
  const hasSession = useAuthStore((s) => Boolean(s.session));
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...inboxKeys.watch, userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/me/watch"));
      return adaptWatch(raw) as WatchItem[];
    },
    staleTime: 30_000,
    enabled: ready && hasSession,
  });
}

export function useRemoveWatchMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (watchId: number) => {
      await callApi(
        api.client.DELETE("/me/watch/{watch_id}", {
          params: { path: { watch_id: watchId } },
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: inboxKeys.watch });
    },
  });
}

export function useNotifySettingsQuery() {
  const ready = useAuthStore((s) => s.ready);
  const hasSession = useAuthStore((s) => Boolean(s.session));
  const userId = useAuthStore((s) => s.session?.userId ?? "anon");
  return useQuery({
    queryKey: [...inboxKeys.notify, userId],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/me/notify-settings"));
      return adaptNotify(raw) as NotifySettings;
    },
    staleTime: 30_000,
    enabled: ready && hasSession,
  });
}

export function useUpdateNotifyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<NotifySettings>) => {
      const raw = await callApi(
        api.client.PUT("/me/notify-settings", {
          body: {
            channels: input.channels,
            event_types: input.eventTypes,
            quiet_start: input.quietStart,
            quiet_end: input.quietEnd,
            daily_cap: input.dailyCap,
            paused: input.paused,
          },
        }),
      );
      return adaptNotify(raw) as NotifySettings;
    },
    onSuccess: (data) => {
      // 只更新当前账号的精确 key；前缀匹配会把 B 的设置写进 A 的缓存。
      const userId = useAuthStore.getState().session?.userId ?? "anon";
      queryClient.setQueryData([...inboxKeys.notify, userId], data);
    },
  });
}

export function useRegisterPushMutation() {
  return useMutation({
    mutationFn: async (input: { token: string; appVersion: string }) => {
      await callApi(
        api.client.POST("/push/register", {
          body: {
            platform: "android",
            provider: "jpush",
            token: input.token,
            app_version: input.appVersion,
          },
        }),
      );
    },
  });
}
