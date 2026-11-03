# ADR-0003 · 前后端接口契约优先，客户端代码生成

- 状态：已采纳
- 日期：2026-11-03

## 背景

前端和后端由 AI 高频修改，手写接口类型会产生漂移。OpenAPI 已由 FastAPI 自动生成，但没有被作为唯一契约。

## 决策

1. FastAPI 是 OpenAPI 的唯一生成源；
2. `packages/api-client` 从 `/openapi.json` 生成 TypeScript 类型与请求 client；
3. 禁止前端手写接口类型；
4. CI 增加 OpenAPI diff 检查；
5. 破坏性变更必须先改后端契约，再同步前端；
6. 生成文件不手改。

## 后果

- 前后端字段漂移会在 CI 被发现；
- AI 修改后端时必须同步契约；
- 前端可依赖生成的类型；
- 需要增加生成脚本与 CI job。
