# 解球 Mobile

Expo React Native + TypeScript。MVP 只做 Android，iOS 后续开启。

## 启动

```bash
# 先确保 packages/api-client/openapi.json 与 schema.d.ts 已更新
corepack pnpm install
cp .env.example .env
corepack pnpm start
corepack pnpm android
```

Android 模拟器访问宿主机后端使用 `http://10.0.2.2:8100`。

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
src/features/         业务切片
src/lib/              env/api/query 基础设施
```

## 约定

- 页面不写业务逻辑；
- 接口类型来自 `@jieqiu/api-client`；
- 文案后续迁入 `packages/i18n`；
- 组件不直接访问数据库或后端 URL。
