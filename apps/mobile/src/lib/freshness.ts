/** 分片数据的新鲜度文案：只描述更新时间，不做“可能过期”式免责。 */
export function ageLabel(capturedAt?: string | null): string {
  if (!capturedAt) return "";
  const ts = Date.parse(capturedAt);
  if (Number.isNaN(ts)) return "";
  const minutes = Math.max(0, Math.floor((Date.now() - ts) / 60000));
  if (minutes < 1) return "刚刚更新";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}
