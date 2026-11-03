import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

export type ApiPaths = paths;
export type ApiClient = ReturnType<typeof createApiClient>;

export interface ApiClientConfig {
  baseUrl: string;
  getToken?: () => string | null | Promise<string | null>;
  getLocale?: () => string | null;
  getMarket?: () => string | null;
  onError?: (status: number, message: string) => void;
}

export interface RequestProfile {
  locale?: string;
  market?: string;
}

function errorMessage(body: unknown, fallback: string): string {
  if (typeof body === "string" && body.trim()) {
    return body;
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (detail != null) {
      return JSON.stringify(detail);
    }
  }
  return fallback;
}

export function createApiClient(config: ApiClientConfig) {
  const client = createClient<paths>({
    baseUrl: config.baseUrl.replace(/\/$/, ""),
  });

  const middleware: Middleware = {
    async onRequest({ request }) {
      // 所有请求统一 12s 超时，避免弱网下无限等待；调用方仍可传入自己的 signal。
      const controller = new AbortController();
      // 计时器在 fetch 结束后即使触发也只是 abort 一个已结算请求，无副作用。
      setTimeout(() => controller.abort(), 12_000);
      request = new Request(request, { signal: controller.signal });
      const token = await config.getToken?.();
      if (token) {
        request.headers.set("Authorization", `Bearer ${token}`);
      }

      const locale = config.getLocale?.();
      if (locale) {
        request.headers.set("Accept-Language", locale);
      }

      const market = config.getMarket?.();
      if (market) {
        request.headers.set("X-Market", market);
      }

      return request;
    },
    onResponse({ response }) {
      if (!response.ok && config.onError) {
        response
          .clone()
          .json()
          .then((body: unknown) => {
            config.onError?.(response.status, errorMessage(body, response.statusText));
          })
          .catch(() => {
            config.onError?.(response.status, response.statusText);
          });
      }
      return undefined;
    },
  };

  client.use(middleware);

  return {
    client,
    baseUrl: config.baseUrl,
  };
}

export type { paths };
