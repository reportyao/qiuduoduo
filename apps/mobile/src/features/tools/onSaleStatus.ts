/** 在售列表的状态文案：不能把 killed 当成“在售”，否则用户会以为这场还有判断。 */
export function onSaleStatusLabel(status: string | null | undefined,
                                  tier?: string | null): string {
  if (tier === "verified") return "预测";
  if (tier === "market_reference") return "预测";
  if (tier === "avoid") return "回避";
  if (tier === "no_data") return "预测";
  if (status === "promoted") return "预测";
  if (status === "screening") return "预测";
  if (status === "killed") return "回避";
  return "在售";
}
