# 解球 monorepo 命令
# 安装 just 后执行：just --list

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
    cd jieqiu-backend && alembic upgrade head

# ---------- 后端（过渡期仍在 jieqiu-backend） ----------

api-install:
    cd jieqiu-backend && python -m pip install -r requirements.txt

api-run:
    cd jieqiu-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

api-test:
    cd jieqiu-backend && python -m pytest -q

api-openapi:
    cd jieqiu-backend && python -c "import json; from app.main import app; print(json.dumps(app.openapi(), ensure_ascii=False))" > ../packages/api-client/openapi.json

# ---------- 前端 ----------

install:
    pnpm install

api-client-install:
    cd packages/api-client && pnpm install

api-client-generate:
    cd packages/api-client && pnpm generate

mobile-install:
    cd apps/mobile && pnpm install

mobile-start:
    cd apps/mobile && pnpm start

mobile-android:
    cd apps/mobile && pnpm android

mobile-ios:
    cd apps/mobile && pnpm ios

mobile-test:
    cd apps/mobile && pnpm test

mobile-lint:
    cd apps/mobile && pnpm lint

mobile-typecheck:
    cd apps/mobile && pnpm typecheck

# ---------- 全量 ----------

check:
    just api-test
    just mobile-typecheck
    just mobile-test

build-android-staging:
    cd apps/mobile && pnpm android:build:staging
