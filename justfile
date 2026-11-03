# 解球 monorepo 命令
# 安装 just 后执行：just --list
# Node 22 自带 corepack；这里统一用 corepack pnpm，避免本机未全局安装 pnpm。

default:
    @just --list

# ---------- 基础 ----------

db-up:
    docker compose up -d postgres

db-down:
    docker compose down

db-reset:
    docker compose down -v && just db-up

db-migrate:
    cd jieqiu-backend && python -m alembic upgrade head

# ---------- 后端（过渡期仍在 jieqiu-backend） ----------

api-install:
    cd jieqiu-backend && python -m pip install -r requirements.txt

api-run:
    cd jieqiu-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

api-test:
    cd jieqiu-backend && python -m pytest -q

api-openapi:
    cd jieqiu-backend && python -c "import json, pathlib; from app.main import app; pathlib.Path('../packages/api-client/openapi.json').write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')"

# ---------- 前端 ----------

install:
    corepack pnpm install

api-client-install:
    cd packages/api-client && corepack pnpm install

api-client-generate:
    just api-openapi
    cd packages/api-client && corepack pnpm generate

api-client-typecheck:
    cd packages/api-client && corepack pnpm typecheck

mobile-install:
    cd apps/mobile && corepack pnpm install

mobile-start:
    cd apps/mobile && corepack pnpm start

mobile-android:
    cd apps/mobile && corepack pnpm android

mobile-ios:
    cd apps/mobile && corepack pnpm ios

mobile-test:
    cd apps/mobile && corepack pnpm test

mobile-lint:
    cd apps/mobile && corepack pnpm lint

mobile-typecheck:
    cd apps/mobile && corepack pnpm typecheck

mobile-bundle:
    cd apps/mobile && corepack pnpm exec expo export --platform android --output-dir .export-check --clear

# ---------- 全量 ----------

check:
    just api-test
    just api-client-typecheck
    just mobile-typecheck
    just mobile-lint
    just mobile-test

build-android-staging:
    cd apps/mobile && corepack pnpm android:build:staging
