import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { usePersonaId } from "@/features/preferences/prefsStore";
import { mergePersonaContent, type PersonaConfigResponse } from "./merge";
import { COPY, PERSONAS, type PersonaCopy, type PersonaMeta } from "./personas";

export interface PersonaContent {
  id: ReturnType<typeof usePersonaId>;
  meta: PersonaMeta;
  copy: PersonaCopy;
}

/**
 * 页面只依赖这个 hook 取人设文案；切换人设时所有订阅组件自动重渲染。
 * 启动拉一次 /personas（5 分钟缓存）；失败/未加载时用 bundled COPY 兜底。
 */
export function usePersonaContent(): PersonaContent {
  const id = usePersonaId();
  const { data } = useQuery({
    queryKey: ["personas"],
    queryFn: async () =>
      (await callApi(api.client.GET("/personas"))) as unknown as PersonaConfigResponse,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  // 避免每次父组件渲染都生成新 meta/copy，导致整棵订阅树无谓重渲染。
  return useMemo(
    () => ({ id, ...mergePersonaContent(id, data, PERSONAS[id], COPY[id]) }),
    [data, id],
  );
}
