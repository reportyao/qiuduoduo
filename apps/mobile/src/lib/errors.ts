export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** FastAPI 的 detail 可能是字符串、数组（校验错误）或对象（业务错误）。 */
export function messageFromBody(body: unknown, fallback = "请求失败，请稍后重试"): string {
  if (typeof body === "string" && body.trim()) return body;
  if (body && typeof body === "object") {
    const rec = body as Record<string, unknown>;
    if (typeof rec.detail === "string" && rec.detail.trim()) return rec.detail;
    if (typeof rec.message === "string" && rec.message.trim()) return rec.message;
    if (Array.isArray(rec.detail) && rec.detail.length > 0) {
      const first = rec.detail[0] as Record<string, unknown> | undefined;
      if (first && typeof first.msg === "string") return first.msg;
    }
    if (rec.detail && typeof rec.detail === "object") {
      const d = rec.detail as Record<string, unknown>;
      if (typeof d.message === "string") return d.message;
    }
  }
  return fallback;
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "网络不稳定，请稍后重试";
}

export function isAuthError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
