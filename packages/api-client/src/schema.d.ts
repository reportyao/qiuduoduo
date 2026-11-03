/**
 * 占位文件：执行 `pnpm generate` 后会被 OpenAPI 生成结果覆盖。
 *
 * 生成命令：
 *   cd packages/api-client
 *   pnpm generate
 *
 * 该文件由 openapi-typescript 生成，禁止手改。
 */
export interface paths {
  "/health": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": {
              status: string;
            };
          };
        };
      };
    };
  };
}
