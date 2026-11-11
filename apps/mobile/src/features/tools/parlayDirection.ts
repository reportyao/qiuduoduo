import type { ParlayDir } from "./parlayStore";

/** 后端 pick.dir 是中文（主胜/平/客胜），早期测试数据是 home/draw/away。 */
export function toParlayDir(raw: string | null | undefined): ParlayDir | null {
  if (raw === "主胜" || raw === "home") return "home";
  if (raw === "平" || raw === "平局" || raw === "draw") return "draw";
  if (raw === "客胜" || raw === "away") return "away";
  return null;
}
