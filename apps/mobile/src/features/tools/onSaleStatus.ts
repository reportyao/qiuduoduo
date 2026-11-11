/** 在售列表的状态文案：不能把 killed 当成“在售”，否则用户会以为这场还有判断。 */
export function onSaleStatusLabel(status: string | null | undefined,
                                  tier?: string | null): string {
  if (tier === "verified") return "核验";
  if (tier === "market_reference") return "市场参考";
  if (tier === "avoid") return "不建议";
  if (tier === "no_data") return "待数据";
  if (status === "promoted") return "已过";
  if (status === "screening") return "复核";
  if (status === "killed") return "未给预测";
  return "在售";
}
