# @jieqiu/api-client

OpenAPI 生成的类型安全 client。

## 生成

**不要对着本地正在跑的 8100 端口生成** —— 那可能是旧进程，会把新接口整体漏掉（历史上曾用 0.7.0-w7 的 8100 生成出 59 条路径，而当时代码已是 71 条；现在当前快照是 **128 路径 / 143 方法**）。

正确流程是从当前代码导出契约快照，再离线生成类型：

```bash
# 仓库根目录
just api-client-generate
```

等价于：

```bash
just api-openapi          # 后端代码 → packages/api-client/openapi.json
cd packages/api-client
corepack pnpm generate    # openapi.json → src/schema.d.ts
```

`openapi.json` 是契约快照，需要随接口变更一起提交，便于 diff 和离线生成。
`src/schema.d.ts` 由 `openapi-typescript` 生成，禁止手改。

仅在联调远端环境时使用：

```bash
pnpm generate:url         # 本机 8100 当前进程（需确认版本）
pnpm generate:staging     # staging
```

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
