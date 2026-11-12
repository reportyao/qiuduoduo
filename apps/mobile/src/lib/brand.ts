/** 用户端统一品牌口径：底层数据源不在 UI 暴露，统一显示为球多多自研AI引擎预测。 */
export function brandCopy(text: string): string {
  return text.replace(/Sportmonks/gi, "球多多自研AI引擎预测");
}
