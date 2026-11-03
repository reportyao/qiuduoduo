export type PersonaId = "zhuanjia" | "laopao" | "meng";

export const PERSONA_ORDER: PersonaId[] = ["zhuanjia", "laopao", "meng"];

export function normalizePersona(value: unknown, fallback: PersonaId = "zhuanjia"): PersonaId {
  return value === "zhuanjia" || value === "laopao" || value === "meng" ? value : fallback;
}
