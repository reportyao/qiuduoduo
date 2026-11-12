/** 用户端不展示底层数据源名称；仅保留真实数据名称。 */
export function brandCopy(text: string): string {
  return text.replace(/Sportmonks\s*·?\s*/gi, "").trim();
}
