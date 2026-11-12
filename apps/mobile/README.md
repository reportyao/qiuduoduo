# 球多多 Mobile

Expo React Native + TypeScript 生产前端。MVP 只做 Android，iOS 后续开启。

v4.1 当前结构：**助理 / 比赛 / 计划 / 我的** 4 Tab，记录移入“我的 → 我的记录”。已实现：年龄门（服务端同步）/ 首页对话流 + HeaderMetrics + 每日 AI 战绩 + Today Hero / 聚焦面板 / 在售与覆盖筛选 / 完整预测与证据 / 记一注与撤销（服务端合规拦截）/ 4 场模拟定投计划（三种风险、Max 门控、历史收益）/ 会员权益页（充值假 UI）/ 串关参谋 / 票单与周报 / 公开账本 / 站内信与关注 / 通知设置 / 合规中心 / 人设与偏好（chat 带 persona）/ 手机号登录与游客数据合并 / 分享落地页。

当前验证（2026-11-12）：**47 个 Vitest**、typecheck、ESLint、Android Hermes bundle 通过；MuMu x86_64 模拟器已走通主要页面。后端 **341 tests / OpenAPI 158 路径 / 174 方法**。正式 APK 签名发布、iOS、真机 JPush 仍未做。

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
