# ADR-0001 · 采用 AI 原生模块化单体

- 状态：已采纳
- 日期：2026-11-03
- 影响范围：后端架构、仓库结构、开发流程
- 实现状态（2026-11-04）：monorepo/mobile/api-client 已落地；后端仍在 `jieqiu-backend/`，`services/api/` 迁移未完成；Web/Admin 仍是规划。

## 背景

未来绝大多数编码工作预计由 AI 完成。AI 开发的瓶颈不是“写代码速度”，而是：

1. 上下文有限；
2. 修改容易扩散；
3. 正确性依赖类型、测试、契约；
4. 部署/迁移/回滚必须可控。

当前后端是 FastAPI 模块化单体，前端是单文件 HTML 原型。继续在单文件原型上开发会放大维护风险。

## 决策

采用：

> **单仓多包 + 模块化单体 + 垂直 feature 切片 + 契约优先 + 强类型/测试/一键命令。**

具体为：

1. 后端继续使用 FastAPI，但按 `app/features/<feature>` 组织；
2. 移动端使用 Expo React Native + TypeScript；
3. Web 使用 Next.js 只做落地页/公开账本/分享；
4. OpenAPI 是前后端唯一接口事实源；
5. Postgres 是生产事实源；
6. Alembic 管理数据库迁移；
7. 使用 monorepo 组织 apps/packages/services。

## 理由

- 模块化单体上下文小，AI 一次只处理一个 feature；
- 契约优先减少幻觉；
- 单仓让接口/类型/文档可原子变更；
- 主流技术栈语料丰富，AI 错误率低；
- 部署和回滚简单；
- 当前用户量不需要微服务。

## 后果

- 需要逐步拆分全局 `models.py`；
- 需要引入 Alembic；
- 需要建立 `packages/api-client`；
- 不允许随意增加新服务；
- feature 间交互必须显式化。
