import type { OddsFormat } from "@/features/preferences/prefsStore";

const CN_OFFSET_MINUTES = 8 * 60;

/** 后端时间字符串是「中国竞彩时间」的 naive 字符串；统一按 +08:00 解析，避免设备时区漂移。 */
export function parseCnDateTime(value: string | null | undefined): Date | null {
  if (!value) return null;
  const raw = value.trim();
  if (!raw) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return new Date(`${raw}T00:00:00+08:00`);
  }
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(raw)) {
    return new Date(`${raw.replace(" ", "T")}+08:00`);
  }
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

function two(n: number): string {
  return String(n).padStart(2, "0");
}

/**
 * 后端部分字段（sealed_at / notification.created_at）是 UTC naive；
 * 在适配层补 Z，避免被 parseCnDateTime 误当中国时间再加 8 小时。
 */
export function utcIso(value: string | null | undefined): string | null {
  if (!value) return null;
  const raw = value.trim();
  if (!raw) return null;
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?$/.test(raw)) {
    return `${raw.replace(" ", "T")}Z`;
  }
  return raw;
}

/** 以中国时区展示时间，不依赖设备时区。 */
export function cnParts(date: Date): { y: number; m: number; d: number; h: number; min: number } {
  const shifted = new Date(date.getTime() + CN_OFFSET_MINUTES * 60_000);
  return {
    y: shifted.getUTCFullYear(),
    m: shifted.getUTCMonth() + 1,
    d: shifted.getUTCDate(),
    h: shifted.getUTCHours(),
    min: shifted.getUTCMinutes(),
  };
}

export function formatTime(value: string | Date | null | undefined): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return "--:--";
  const p = cnParts(d);
  return `${two(p.h)}:${two(p.min)}`;
}

export function formatDate(value: string | Date | null | undefined): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return "--";
  const p = cnParts(d);
  return `${p.m}月${p.d}日`;
}

export function formatDateShort(value: string | Date | null | undefined): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return "--";
  const p = cnParts(d);
  return `${p.m}/${p.d}`;
}

export function formatDateTime(value: string | Date | null | undefined): string {
  return `${formatDate(value)} ${formatTime(value)}`;
}

export function todayCn(): string {
  const p = cnParts(new Date());
  return `${p.y}-${two(p.m)}-${two(p.d)}`;
}

export function dateCnOffset(days: number): string {
  const d = new Date(Date.now() + days * 86_400_000);
  const p = cnParts(d);
  return `${p.y}-${two(p.m)}-${two(p.d)}`;
}

export function yesterdayCn(): string {
  return dateCnOffset(-1);
}

/**
 * 竞彩日界：00:00–04:59 开赛的场次属于前一日销售日。
 * 用于 watch/on-sale/inbox 深链选择正确的 trade_date。
 */
export function tradeDateCnFromKickoff(value: string | Date | null | undefined): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return todayCn();
  const p = cnParts(d);
  let ts = Date.UTC(p.y, p.m - 1, p.d);
  if (p.h < 5) ts -= 86_400_000;
  const shifted = new Date(ts);
  return `${shifted.getUTCFullYear()}-${two(shifted.getUTCMonth() + 1)}-${two(shifted.getUTCDate())}`;
}

export function shiftDateCn(date: string, days: number): string {
  const d = parseCnDateTime(date);
  if (!d) return date;
  return dateCnOffsetFrom(d, days);
}

function dateCnOffsetFrom(date: Date, days: number): string {
  const p = cnParts(date);
  const shifted = new Date(Date.UTC(p.y, p.m - 1, p.d) + days * 86_400_000);
  return `${shifted.getUTCFullYear()}-${two(shifted.getUTCMonth() + 1)}-${two(shifted.getUTCDate())}`;
}

/** 当前销售日（凌晨 5 点前仍算前一天）。 */
export function currentTradeDateCn(now = Date.now()): string {
  return tradeDateCnFromKickoff(new Date(now));
}

export function weekdayCn(value: string | Date | null | undefined): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return "";
  const p = cnParts(d);
  // 用中国日期重新构造 UTC 零点再取星期，避免 +08:00 凌晨场被算到前一天。
  const day = new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay();
  const labels = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return labels[day];
}

/** 距停售的倒计时；返回文案而不是负数，页面不需要自己判断。 */
export function countdownText(value: string | Date | null | undefined, now = Date.now()): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return "停售时间待同步";
  const diff = d.getTime() - now;
  if (diff <= 0) return "已停售";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins} 分钟`;
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  return rest > 0 ? `${hours} 小时 ${rest} 分` : `${hours} 小时`;
}

/** 列表用：倒计时 + “停售”，已停售/待同步不重复后缀。 */
export function saleCountdownText(value: string | Date | null | undefined, now = Date.now()): string {
  const text = countdownText(value, now);
  return text === "已停售" || text === "停售时间待同步" ? text : `${text}停售`;
}

export function relativeTime(value: string | Date | null | undefined, now = Date.now()): string {
  const d = value instanceof Date ? value : parseCnDateTime(value);
  if (!d) return "刚刚更新";
  const sec = Math.max(0, Math.floor((now - d.getTime()) / 1000));
  if (sec < 10) return "刚刚更新";
  if (sec < 60) return `${sec} 秒前更新`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前更新`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前更新`;
  return `${Math.floor(hour / 24)} 天前更新`;
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "--";
  return `${(value * 100).toFixed(digits)}%`;
}

export function pp(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "--";
  const n = value * 100;
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}pp`;
}

export function signedPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "--";
  const n = value * 100;
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

export function money(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "--";
  const sign = value < 0 ? "-" : "";
  return `${sign}¥${Math.abs(value).toFixed(digits)}`;
}

export function signedMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "--";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}¥${Math.abs(value).toFixed(0)}`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function normalizeProbs(sp: { h: number; d: number; a: number }): {
  home: number;
  draw: number;
  away: number;
} {
  const inv = [1 / sp.h, 1 / sp.d, 1 / sp.a];
  const total = inv.reduce((sum, v) => sum + v, 0);
  return { home: inv[0] / total, draw: inv[1] / total, away: inv[2] / total };
}

/** 官方抽水 = overround / (1 + overround)。与后端 rake 字段同口径。 */
export function impliedRake(sp: { h: number; d: number; a: number }): number {
  const overround = 1 / sp.h + 1 / sp.d + 1 / sp.a - 1;
  return overround / (1 + overround);
}

export function decimalToFormat(decimal: number, format: OddsFormat): string {
  if (!Number.isFinite(decimal) || decimal <= 1) return "--";
  if (format === "hk") return (decimal - 1).toFixed(2);
  if (format === "indo") {
    const v = decimal >= 2 ? decimal - 1 : -1 / (decimal - 1);
    return v.toFixed(2);
  }
  if (format === "american") {
    const v = decimal >= 2 ? (decimal - 1) * 100 : -100 / (decimal - 1);
    return v > 0 ? `+${v.toFixed(0)}` : v.toFixed(0);
  }
  return decimal.toFixed(2);
}

export function oddsFormatLabel(format: OddsFormat): string {
  return { decimal: "欧洲盘", hk: "香港盘", indo: "印尼盘", american: "美式盘" }[format];
}

export function pickDirectionLabel(pool: string, dir: string | null | undefined): string {
  if (!dir) return "暂无预测";
  // 后端接口用中文方向（主胜/平局/客胜），早期前端测试用 home/draw/away；两种都认。
  const key = ({ 主胜: "home", 平: "draw", 平局: "draw", 客胜: "away" } as Record<string, string>)[dir] ?? dir;
  const isHhad = pool === "hhad";
  if (key === "home") return isHhad ? "让球主胜" : "主胜";
  if (key === "draw") return isHhad ? "让球平" : "平局";
  if (key === "away") return isHhad ? "让球客胜" : "客胜";
  return dir;
}

export function gateLabel(gate: string): string {
  return { price: "价", market: "市", model: "模" }[gate] ?? gate;
}

export function gateResultLabel(result: string | null | undefined): string {
  return { pass: "通过", fail: "未通过", pending_data: "待数据" }[result ?? ""] ?? "待定";
}

export function shortHash(hash: string | null | undefined, head = 8, tail = 4): string {
  if (!hash) return "未封存";
  if (hash.length <= head + tail + 1) return hash;
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}
