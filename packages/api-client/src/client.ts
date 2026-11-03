import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

export type ApiPaths = paths;
export type ApiClient = ReturnType<typeof createApiClient>;

export interface ApiClientConfig {
  baseUrl: string;
  getToken?: () => string | null;
  getLocale?: () => string | null;
  getMarket?: () => string | null;
  onError?: (status: number, message: string) => void;
}

export interface RequestProfile {
  locale?: string;
  market?: string;
}

export function createApiClient(config: ApiClientConfig) {
  const client = createClient<paths>({
    baseUrl: config.baseUrl.replace(/\/$/, ""),
  });

  const middleware: Middleware = {
    onRequest({ request }) {
      const token = config.getToken?.();
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
            const message =
              typeof body === "object" && body && "detail" in body
                ? String((body as { detail: unknown }).detail)
                : response.statusText;
            config.onError?.(response.status, message);
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
