import { ApiError, messageFromBody } from "./errors";

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * openapi-fetch 不会抛错；统一在这里把 error/HTTP 状态转成 ApiError。
 * 页面层只处理 ApiError + 重试，不再各自判断 response.ok。
 */
export async function callApi<T>(request: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok || error !== undefined) {
    throw new ApiError(
      response.status,
      messageFromBody(error ?? data, `请求失败（${response.status}）`),
      error ?? data,
    );
  }
  if (data === undefined) {
    throw new ApiError(response.status, "服务端没有返回数据");
  }
  return data;
}
