import type { PersonaCopy, PersonaMeta } from "./personas";
import type { PersonaId } from "./personaIds";

export interface PersonaConfigProfile {
  id: string;
  name: string;
  address: string;
  tone: string;
}

export interface PersonaConfigSlot {
  persona_id: string;
  slot_key: string;
  template: string;
}

export interface PersonaConfigResponse {
  version: number;
  profiles: PersonaConfigProfile[];
  slots: PersonaConfigSlot[];
}

/** 后台可覆盖的简单文案字段；带逻辑的函数文案仍保留在前端。 */
export const SLOT_COPY_KEYS = [
  "brandSub",
  "saleTitle",
  "parlayTitle",
  "parlaySub",
  "parlayCta",
  "typing",
  "emptyTitle",
  "emptyBody",
  "restTitle",
  "restBody",
  "chatGreeting",
  "whyNotLead",
] as const;

type SlotKey = (typeof SLOT_COPY_KEYS)[number];

export function mergePersonaContent(
  id: PersonaId,
  config: PersonaConfigResponse | null | undefined,
  baseMeta: PersonaMeta,
  baseCopy: PersonaCopy,
): { meta: PersonaMeta; copy: PersonaCopy } {
  if (!config) return { meta: baseMeta, copy: baseCopy };

  const profile = config.profiles.find((item) => item.id === id);
  const meta: PersonaMeta = {
    ...baseMeta,
    name: profile?.name || baseMeta.name,
    tag: profile?.tone || baseMeta.tag,
    address: profile?.address || baseMeta.address,
  };

  const slots = new Map<string, string>();
  for (const slot of config.slots) {
    if (slot.persona_id === id) slots.set(slot.slot_key, slot.template);
  }

  const copy: PersonaCopy = { ...baseCopy };
  for (const key of SLOT_COPY_KEYS) {
    const template = slots.get(key);
    if (!template) continue;
    (copy as Record<SlotKey, string>)[key] = template.split("{address}").join(meta.address);
  }
  return { meta, copy };
}
