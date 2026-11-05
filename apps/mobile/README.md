# 球多多 Mobile

Expo React Native + TypeScript 生产前端。MVP 只做 Android，iOS 后续开启。

当前已实现：年龄门（服务端同步）/ 首页判决流 + Today Hero（方向/成立条件/失效条件/AI 复核徽章）/ 首页聚焦面板（覆盖率/事实/未知项/可用动作）/ 真实数据脉搏指标与数据状态页 / 在售与选择器覆盖筛选 / 完整账 / 情报与证据 / 封存验证 / 记一注与 5 秒撤销（服务端合规拦截）/ 助理对话 / 8 个工具 / 串关体检 + 组合参谋（published 优先、preview 回退）/ 票单与周报 / 公开账本 / 站内信 / 关注 / 通知设置 / 合规中心（自排除/PGSI 服务端闭环）/ 人设与偏好 / 手机号登录与游客数据合并 / 分享落地页 `/s/{id}` / 最小互动埋点（`/interactions`）。

当前验证（2026-11-05）：22 个 Vitest、typecheck、ESLint、Android Hermes bundle 通过；真实 Android APK/iOS 原生构建仍需 EAS/本机构建环境。后端当前 251 tests / OpenAPI 128 路径 / 143 方法。

**交接先读 [ARCHITECTURE.md](./ARCHITECTURE.md)**：目录、路由、数据适配、会话合并、已知后端缺口都在那里。

## 启动

```bash
# 先确保 packages/api-client/openapi.json 与 schema.d.ts 已更新
corepack pnpm install
cp .env.example .env
corepack pnpm start
corepack pnpm android
```

Android 模拟器访问宿主机后端使用 `http://10.0.2.2:8100`，iOS 模拟器使用 `http://127.0.0.1:8100`（未配置 `EXPO_PUBLIC_API_BASE_URL` 时的本地兜底）。

**发布包必须显式注入 `EXPO_PUBLIC_API_BASE_URL=https://...`**：Android release 默认禁止明文 HTTP，iOS ATS 也不允许任意 HTTP；不要依赖模拟器地址。当前 `src/lib/env.ts` 在非 development/release 构建下会直接抛错，防止把 `10.0.2.2` 打进包。

## 构建前自检

```bash
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm test
# 真正跑 Metro + Hermes 出 Android bundle，能抓到 typecheck 抓不到的解析错误
corepack pnpm exec expo export --platform android --output-dir .export-check --clear
```

仓库根 `.npmrc` 固定 `node-linker=hoisted`：Windows + pnpm 严格布局下路径过长会让
`hermesc.exe` 报 `ERROR_INSUFFICIENT_BUFFER`，不要改回 isolated。

## 结构

```text
app/                  Expo Router 路由薄壳
src/features/         业务切片（queries/components/文案）
src/domain/           领域模型 + API 响应适配器
src/components/       全局 UI 原语 / Header / 自定义底栏
src/lib/              env/api/query/storage/format 基础设施
src/theme/            设计令牌
```

## 约定

- 页面不写业务逻辑；
- 接口类型来自 `@jieqiu/api-client`，响应经 `src/domain/*Adapters.ts` 降级；
- 用户数据 queryKey 必须带 userId；登录相关查询必须等 authReady；
- 文案走人设/常量，不在组件里散落；
- 组件不直接访问数据库或后端 URL。
