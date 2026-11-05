/** 在售列表的状态文案：不能把 killed 当成“在售”，否则用户会以为这场还有判断。 */
export function onSaleStatusLabel(status: string | null | undefined): string {
  if (status === "promoted") return "已过";
  if (status === "screening") return "复核";
  if (status === "killed") return "已砍";
  return "在售";
}
