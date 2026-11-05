/** 公开账本会同时列出已推、复核中和已砍的场次，行内必须标清发布状态。 */
export function ledgerStatusLabel(status: string): string {
  if (status === "promoted") return "已推";
  if (status === "killed") return "已砍";
  if (status === "screening") return "复核中";
  return "未定";
}
