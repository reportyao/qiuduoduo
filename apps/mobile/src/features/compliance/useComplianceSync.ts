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
  const query = useQuery({
    queryKey: ["compliance-state", session?.userId ?? "anon"],
    queryFn: async () => {
      const raw = await callApi(api.client.GET("/compliance/state"));
      return record(raw);
    },
    enabled: Boolean(session),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!query.data) return;
    const exclusion = record(query.data.self_exclusion);
    const until = nullableString(exclusion.until);
    const local = useComplianceStore.getState();
    const serverActive = Boolean(until) || Boolean(exclusion.permanent);
    // 服务端不可用/尚未写入时，不能清掉本机已生效的自排除（离线也拦截）。
    if (!serverActive && (local.excludedPermanent || isExcluded(local.excludedUntil))) return;
    apply({
      excludedUntil: until ? Date.parse(until) : null,
      excludedAt: until ? Date.now() : null,
      excludedPermanent: Boolean(exclusion.permanent),
      pgsiScore: null,
      pgsiAt: null,
    });
    // 服务端未成年锁定优先于本机：清缓存/换设备也不能绕过。
    if (query.data.under18_locked) {
      usePrefsStore.getState().setAgeDecision("minor");
    }
  }, [apply, query.data]);
}
