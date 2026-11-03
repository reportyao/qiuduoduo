# @jieqiu/api-client

OpenAPI 生成的类型安全 client。

## 生成

后端启动后：

```bash
cd packages/api-client
pnpm install
pnpm generate
```

`src/schema.d.ts` 由 `openapi-typescript` 生成，禁止手改。

## 使用

```ts
import { createApiClient } from "@jieqiu/api-client";

const api = createApiClient({
  baseUrl: "https://api.jieqiu.example",
  getToken: () => token,
  getLocale: () => "zh-CN",
  getMarket: () => "cn",
});

const { data } = await api.client.GET("/health");
```

## 规则

- 前端不得手写接口类型；
- 后端破坏性变更先改 OpenAPI；
- CI 需要跑 `openapi-diff`（后续接入）。
