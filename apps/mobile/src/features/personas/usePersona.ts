import { COPY, PERSONAS, type PersonaCopy, type PersonaMeta } from "./personas";
import { usePersonaId } from "@/features/preferences/prefsStore";

export interface PersonaContent {
  id: ReturnType<typeof usePersonaId>;
  meta: PersonaMeta;
  copy: PersonaCopy;
}

/** 页面只依赖这个 hook 取人设文案；切换人设时所有订阅组件自动重渲染。 */
export function usePersonaContent(): PersonaContent {
  const id = usePersonaId();
  return { id, meta: PERSONAS[id], copy: COPY[id] };
}
