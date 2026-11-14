import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./errors";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 20_000,
        gcTime: 10 * 60_000,
        refetchOnWindowFocus: false,
        // 断网时先展示缓存，不把离线当错误；恢复联网由 OfflineBanner 统一重取。
        networkMode: "offlineFirst",
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 2;
        },
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
