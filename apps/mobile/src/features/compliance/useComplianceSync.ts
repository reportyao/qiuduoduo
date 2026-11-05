import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { record, nullableString } from "@/lib/parse";
import { useAuthStore } from "@/features/auth/authStore";
import { isExcluded, useComplianceStore } from "./complianceStore";
import { usePrefsStore } from "@/features/preferences/prefsStore";

/** 登录/设备身份就绪后，用服务端合规状态覆盖本机缓存（重装/换设备不可绕过）。 */
export function useComplianceSync(): void {
  const session = useAuthStore((s) => s.session);
  const apply = useComplianceStore((s) => s.applyServerState);
  const markSynced = useComplianceStore((s) => s.markSynced);
  const query = useQuery({
    queryKey: ["compliance-state", session?.userId ?? "anon"],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/compliance/state"));
      return record(raw);
    },
    enabled: Boolean(session),
    staleTime: 30_000,
  });
  const data = query.data;
  const refetch = query.refetch;

  useEffect(() => {
    if (!data) return;
    const exclusion = record(data.self_exclusion);
    const until = nullableString(exclusion.until);
    const local = useComplianceStore.getState();
    const serverActive = Boolean(until) || Boolean(exclusion.permanent);
    const localActive = local.excludedPermanent || isExcluded(local.excludedUntil);
    // 服务端不可用/尚未写入时，不能清掉本机已生效的自排除（离线也拦截）。
    if (!serverActive && localActive) {
      // 本机生效但服务端未确认：联网后补写，否则换设备/重装仍可绕过。
      if (!local.syncPending) return;
      const days = local.excludedPermanent || local.excludedUntil == null
        ? null
        : Math.max(1, Math.ceil((local.excludedUntil - Date.now()) / 86_400_000));
      void callApi(api.client.POST("/compliance/self-exclusion", {
        body: {
          days,
          permanent: local.excludedPermanent,
          reason: "user_self_exclusion_retry",
        },
      }))
        .then(() => {
          markSynced();
          void refetch();
        })
        .catch(() => {});
      return;
    }
    if (!serverActive) {
      apply({
        excludedUntil: null,
        excludedAt: null,
        excludedPermanent: false,
        pgsiScore: null,
        pgsiAt: null,
      });
      return;
    }
    apply({
      excludedUntil: until ? Date.parse(until) : null,
      excludedAt: until ? Date.now() : null,
      excludedPermanent: Boolean(exclusion.permanent),
      pgsiScore: null,
      pgsiAt: null,
    });
    // 服务端未成年锁定优先于本机：清缓存/换设备也不能绕过。
    if (data.under18_locked) {
      usePrefsStore.getState().setAgeDecision("minor");
    }
  }, [apply, data, markSynced, refetch]);
}
