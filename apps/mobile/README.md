# 解球 Mobile

Expo React Native + TypeScript。MVP 只做 Android，iOS 后续开启。

## 启动

```bash
# 先确保 packages/api-client/src/schema.d.ts 已由后端 OpenAPI 生成
pnpm install
cp .env.example .env
pnpm start
pnpm android
```

Android 模拟器访问宿主机后端使用 `http://10.0.2.2:8100`。

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
