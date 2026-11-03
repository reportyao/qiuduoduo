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
  let result: FetchResult<T>;
  try {
    result = await request;
  } catch (error) {
    // openapi-fetch 在网络失败时会直接 reject（未注册 onError 时）；
    // 统一转成 ApiError(0)，让页面错误文案/重试逻辑保持一致。
    throw new ApiError(0, "网络连接失败，请检查网络后重试", error);
  }
  const { data, error, response } = result;
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
