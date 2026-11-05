/**
 * 公开账本列出的是判决复核状态，不是发布状态：
 * promoted 只代表三关全过，是否 published 由推荐主链另行决定。
 */
export function ledgerStatusLabel(status: string): string {
  if (status === "promoted") return "过三关";
  if (status === "killed") return "已砍";
  if (status === "screening") return "复核中";
  return "未定";
}
