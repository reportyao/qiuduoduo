# 球多多 · LLM Gateway 与多模型路由（Phase 1 已实现）

> **状态：Phase 1 已实现。** `llm_usage`/`llm_cache`/`llm_budgets` 三张表与迁移 `20261104_07` 已落；`/chat` 的登录用户 fallback 已接入 `open_chat → fast`，失败/无 Key/超预算/超时/schema 失败一律回到固定引导；后台 `/admin` 模型用量页已展示 profile 状态、今日用量、预算与最近调用。`match_analysis → deep`、`analysis_jobs`、`ai_analyses`、`intel_items` 仍待 Phase 2；`narrate.py` 先读 `persona_copy_cache`，未命中走确定性模板，不在请求时调 LLM。审核任务 `decision_review` / `adversarial_review` / `plan_review` 已接入；persona 的实际 HTTP 调用也统一走 `llm_gateway.call_profile`，模型池/熔断仍由 persona 子系统管理。
>
> 目标：用 **两条车道 + 任务路由 + 缓存 + 原子预算 + 异步分析** 接入多个模型，而不是每条消息都调一次 LLM。
>
> 关联：[聚焦决策流](./focused-decision-flow.md) · [数据库架构](./database-architecture.md) · [TechSpec §8](../TechSpec-v2.1.md) · [Intelligence-Layer](../Intelligence-Layer-v1.0.md)

## 1. 总体结构

```text
chat.py / narrate.py / focus interpretation
        ↓
Intent Router（规则优先，固定意图 0 LLM）
        ↓
LLMGateway.complete(task, messages, schema)
        ↓
Task Route：copy_polish / open_chat / match_analysis / json_repair
        ↓
Profile：fast（免费/低成本） / deep（DeepSeek） / none（模板）
        ↓
缓存 → 预算原子预占 → HTTP 调用 → 校验 → 记账 → 返回
        ↓
失败/超时/超预算 → fallback profile → 模板
```

核心原则：

- **固定意图不调 LLM**：今晚买啥、为什么不推、复盘、某队查询、抽水、串关，全部走规则/模板/数据。
- **free 模型做通用文案和开放问答**；DeepSeek 只做数据齐全的深读分析。
- **预测不交给 LLM**：概率、三闸、抽水仍由统计模型和确定性代码产出。
- **动作按钮不调 LLM**：按钮是确定性动作，只有自由提问才可能进入 LLM。
- **无 key / 超时 / 超预算 / 校验失败**：一律模板兜底，不阻塞判决。

## 2. 任务矩阵

| task | profile | 用途 | 约束 |
|---|---|---|---|
| `copy_polish` | fast | 人设文案、通知改写、卡片摘要、推荐观点委婉化 |
| `decision_review` | deep | L1–L5 发布前复核；规则为主，LLM 为可选增强 | schema JSON；无 Key 时标记降级，不阻塞规则门 |
| `adversarial_review` | deep | 对抗复核：找反例/失效条件（L4 可选增强） | 同 decision_review；当前规则门为主 |
| `plan_review` | fast | 组合腿/覆盖/风险复核 | 同上 |
| `persona_translate` | persona pool | 人设语气翻译 | 走 `call_profile`；模型池/熔断/缓存独立 |
| `open_chat` | fast | 开放问答、跑题引导、FAQ | 只带公开事实；默认收起；配额 |
| `match_analysis` | deep | 单场深度分析、情景/风险解释 | 仅 `coverage.level=full`；异步/缓存 |
| `json_repair` | fast | JSON 修复、格式重写 | 不产生新事实 |
| `moderation` | none | 禁用词/风险扫描 | 规则/词表；不用 LLM |
| `prediction` | none | 概率/推荐 | **禁止调用任何 LLM** |

路由不是“按消息内容猜”，而是先由 `chat.py` 的规则识别 intent；只有 fallback/开放问题才进入 `open_chat`。深读分析由 `analysis_jobs` 触发，不在聊天主链路同步调用。

## 3. Profile 与配置

第一版只支持两个 profile，避免一上来做“模型市场”：

```env
# fast：免费/低成本模型（GLM-4-Flash、其他 OpenAI-compatible）
JQ_LLM_FAST_PROVIDER=glm
JQ_LLM_FAST_BASE_URL=https://open.bigmodel.cn/api/paas/v4
JQ_LLM_FAST_MODEL=glm-4-flash
JQ_LLM_FAST_API_KEY=...

# deep：DeepSeek
JQ_LLM_DEEP_PROVIDER=deepseek
JQ_LLM_DEEP_BASE_URL=https://api.deepseek.com/v1
JQ_LLM_DEEP_MODEL=deepseek-chat
JQ_LLM_DEEP_API_KEY=...

# 全局
JQ_LLM_TIMEOUT_S=20
JQ_LLM_MAX_RETRIES=1
JQ_LLM_DAILY_BUDGET_CNY=50
```

约定：

- Key 只走 env/KMS；数据库不存明文。
- Provider 端点只允许内置适配器；不允许后台填任意 `base_url`（SSRF）。
- 模型名要固定版本，不用会漂移的别名；换模型走配置版本/审计。
- `fast` 不是“无限免费”：仍要 RPM/TPM 限流、超时、熔断和备用 profile。
- 免费档的数据条款要先审：用户记忆、注单、连败等个人数据不发给免费模型。

### 3.1 Provider 适配器

不要假设所有厂商都是同一种协议；第一版只支持 OpenAI-compatible 与两个内置差异：

| kind | 认证 | 路径 | 备注 |
|---|---|---|---|
| `openai_compatible` | `Authorization: Bearer` | `/chat/completions` | 通用；base_url 必须 HTTPS + 允许列表 |
| `glm` | `Authorization: Bearer` | `/chat/completions` | Base URL 由代码/环境固定，后台不可改 |
| `deepseek` | `Authorization: Bearer` | `/chat/completions` | 同上 |

适配器只做：请求体/响应体/错误码/用量字段归一化；不把厂商 SDK 散落到业务代码。  
超时、重试、熔断、JSON mode 不支持时的降级都在 Gateway 层处理。

### 3.2 用户层级与额度

| 用户 | 固定意图 | 开放问答 | 深读解读 |
|---|---|---|---|
| 匿名 | 模板/卡片，0 LLM | 固定引导，0 LLM | 不提供 |
| 注册免费 | 0 LLM | fast，严格日配额 | 不提供/每日 1 次体验 |
| 订阅会员 | 0 LLM | fast，较高配额 | deep，按 eligible 场次 + 次数 |
| 后台/批量 | — | fast 文案变体 | deep 预生成/审核 |

Phase 1 已在 Gateway 内实现按 CN 自然日的用户/匿名会话调用上限（`JQ_LLM_USER_DAILY_CALLS`，默认 50），缓存命中与拦截不计；全局/任务预算同时生效。`analysis_jobs` 入队前的额度检查随 Phase 2 落地。订阅未上线前，deep 不向免费用户开放。

用户额度实现：

- `llm_usage` 带 `user_id`/`session_id`，按日聚合；匿名只存随机 session。
- 每用户/设备限额可用 Redis 原子计数（推荐）或 `llm_usage` 日聚合；不要只查“最近 N 条”做判断。
- 用户额度与全局 `llm_budgets` 同时生效：先用户额度，再全局预算。
- 超限返回模板/固定引导，不返回 429 或空白。

## 4. 数据表

建议新增：

```text
llm_profiles            -- Phase 3（当前 profile 走 env）
  id, name (fast/deep/backup), kind (glm|deepseek|openai_compatible),
  base_url, model, api_key_env, timeout_s, max_tokens,
  input_price_cny_per_m, output_price_cny_per_m, price_version,
  enabled, created_at, updated_at

llm_routes              -- Phase 3（当前 TASK_PROFILE 固定在代码里）
  task PK, profile, fallback_profile,
  max_tokens, temperature, daily_budget_cny, enabled, updated_at

llm_usage               -- ✅ 已实现
  id, request_id, user_id, session_id, task, profile, provider, model,
  input_tokens, output_tokens, cost_cny, price_version,
  latency_ms, status, cache_hit, error_class, created_at
  index(user_id, created_at), index(task, created_at)

llm_cache               -- ✅ 已实现
  cache_key PK, task, profile, model, prompt_ver,
  scope (public|user_private),
  input_hash, response_json, expires_at, hit_count, created_at
  -- user_private 的 key 必须带 user_id/会话作用域，禁止跨用户命中；Phase 1 用 public/user_private

llm_budgets             -- ✅ 已实现（global 行 task='*', profile='*'）
  day, task, profile, limit_cny, reserved_cny, spent_cny, updated_at
  PK(day, task, profile)
```

与聚焦决策流共用：

- `analysis_jobs`：深读分析异步队列；
- `ai_analyses`：解读结果、prompt/model/cost/缓存；
- `intel_items` / `match_coverage`：事实包和资格判断。

迁移建议：

- `20261104_07_llm_gateway.py`：已落 `llm_usage`/`llm_cache`/`llm_budgets`；
- 聚焦/情报表（`intel_items`/`match_coverage`/`pulse_daily`）：待落，用下一个可用迁移号（当前 head `20261105_12`）；
- 都要求 up/down；生产只 `alembic upgrade head`。

### 预算必须原子

不能“先查余额再调用”。调用前按 `max_tokens` 预估成本，原子预占：

```text
UPDATE llm_budgets
SET reserved_cny = reserved_cny + :estimate
WHERE day=:day AND task=:task AND profile=:profile
  AND spent_cny + reserved_cny + :estimate <= limit_cny
RETURNING ...
```

没有返回行 → 超预算 → 模板。调用完成后按实际 tokens 结算：`reserved -= estimate; spent += actual`。Postgres 用行锁/原子 UPDATE；不要用进程内计数器。进程崩溃留下的 `reserved` 超过 10 分钟后，在下一次预占时回收。

## 5. Gateway 接口

```python
class LLMGateway:
    def complete(
        self,
        task: str,
        messages: list[dict],
        *,
        schema: dict | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        deadline_ms: int | None = None,
    ) -> LLMResult: ...

@dataclass
class LLMResult:
    text: str | None
    data: dict | None
    provider: str
    model: str
    prompt_ver: str
    cached: bool
    usage: dict
    degraded: bool
    error_class: str | None
```

调用顺序：

1. 解析 route/profile；未配置/禁用 → `degraded=True`。
2. 计算 `cache_key = sha256(task + input_hash + prompt_ver + profile + model)`；命中且未过期 → 返回，记 `cache_hit`。
3. 原子预占预算；失败 → 模板。
4. HTTP 调用（OpenAI-compatible `/chat/completions`；适配器处理 GLM/DeepSeek 差异）。
5. 解析 JSON/schema；数字白名单、禁用词、长度、概率语法校验。
6. 失败分类：429/5xx 可重试 1 次；超时/4xx/schema 失败不重试；校验失败最多重试 1 次。
7. 成功 → 记 usage、写 cache、返回；失败 → fallback profile → 模板。
8. 每个 profile 独立熔断；连续失败 N 次暂停 M 分钟。

## 6. 缓存与成本

缓存 key 必须包含：

```text
# Phase 1（open_chat）实际 key：
task + input_hash(messages/schema/max_tokens/temperature)
+ prompt_ver + profile + model + scope(+user/session)

# Phase 2（深读）再追加：
data_cutoff + persona + locale + resolved_entities
```

TTL 建议：

| 内容 | TTL |
|---|---|
| 公共比赛分析（Phase 2） | 绑定 `data_cutoff`；数据更新即失效 |
| 文案变体 | 24h–7d |
| FAQ/开放问答 | 30–60min |
| 用户私有聊天（已实现） | 不跨用户缓存；短期会话缓存 |
| 错误/降级 | 不缓存 |

成本控制：

- 按 task/profile 的日预算；80% 告警，100% 降级。
- `max_tokens` 硬上限；不把完整聊天历史塞进 prompt；只带最近 3–5 轮 + 槽位 + 事实包。
- 同一场比赛的深读分析所有用户共享；三套人设只做外层改写，不重复跑 DeepSeek。
- 批量文案在夜间生成，聊天只读缓存。
- 记录 `cache_hit / cost / latency / degraded`，每周复盘调用率。

### 6.1 深读任务调度

- 只对 `deep_eligible=true` 的场次入队；不满足直接返回模板。
- 优先级：promoted > 临近停售的 screening > 普通 screening；`not_before`/`priority` 入 `analysis_jobs`。
- 赛前预生成：在停售前留出足够时间（建议 ≥30 分钟）；停售后不再发起新的 deep 调用，只读缓存。
- 幂等：`input_hash` 唯一；worker 抢锁 `locked_at`，失败指数退避，最多 2–3 次。
- `ai_analyses` 只存**事实分析**（人设无关）；`narrative_pool` 存每个人设外层文案。禁止三套 DeepSeek。
- 若分析生成晚于数据更新，标 `stale` 并重新排队；不要拿旧分析当新结论。

### 6.2 PII 与免费模型

- 发 fast 前先脱敏：手机号/邮箱/用户 ID、注单金额、连败次数、记忆内容不进 prompt。
- 个人化问题（“我连败几场”“我的注单”）继续走结构化接口，不走 `open_chat`。
- 免费档只接收公开比赛事实/文案；个人数据需要不训练数据的付费档或纯模板。
- prompt/响应日志脱敏；不记录 Authorization、Key、原始设备号。

## 7. 提示词与输出

- 每个 task 一个 prompt 版本；persona 卡只影响 `copy_polish`/外层改写，不影响事实。
- 深读分析输入=确定性事实包；输出 JSON：

```json
{
  "text": "……",
  "facts_used": ["f1", "f3"],
  "unknowns": ["首发未确认"],
  "tone": "zhuanjia"
}
```

- 数字用锁定槽位/占位符注入，不让 LLM 自由写数字；如果必须写，逐项对白名单。
- 禁止“会赢/稳赚/保证”等承诺；推荐观点只用“倾向/参考组合/把握度”，数字/方向/条件由模型与规则锁定；输出过 `scan_text` 和概率语法检查。
- 事实不足时输出 `unknowns`，不补编；`match_analysis` 只对 coverage 达标场次调用。

## 8. 管理后台 `/admin` 模型用量页

当前已实现（只读）：

1. **Profile 状态**：fast/deep 是否配置、provider、model；Key 只显示“已配置/未配置”。
2. **今日用量**：按 task/profile 的调用数、tokens、成本、缓存命中。
3. **预算**：全局/任务上限、已用、预占。
4. **最近调用**：状态、错误分类、延迟、成本、是否缓存命中。

尚未实现（后台改配置/审计）：

- 测试按钮、路由编辑、max_tokens/温度、启停、熔断开关；
- p95/失败率聚合、A/B/影子；
- 改路由/预算写 `admin_audit` 与回滚。

约束：

- 后台只展示环境变量里的内置 profile，不允许任意 URL。
- Key 只显示“已配置/未配置”，不显示明文。
- `/admin` 模型用量页当前只读；人设文案页已有模型/Key/槽位写操作（HttpOnly cookie 会话），并已接入 `admin_audit`。CSRF token 已接入；给模型用量页加写操作前仍需先补限流与审计。

## 9. 接入点

| 业务 | 接入方式 |
|---|---|
| `chat.py` 的 `fallback` | ✅ 登录用户 `open_chat` → fast；匿名固定引导；固定 intent 不调用 |
| `narrate.py` / 变体池 | 读 `persona_copy_cache`；miss 走模板；`copy_polish`/变体池待接 |
| `GET /matches/{id}/focus` 的 `interpretation` | 读 `ai_analyses` 缓存；没有则返回 null/模板，不现场调 deep（待 Phase 2） |
| 深读分析 | `analysis_jobs` → worker → `match_analysis` → deep → 审核/发布（待 Phase 2） |
| 通知文案 | `copy_polish` → fast；中性/禁用词校验（待接） |
| 推荐观点/组合文案 | `copy_polish` → fast，只做委婉化/结构化；方向/概率/条件由模型与规则锁定，AI 复核后发布 |
| 预测/三闸/抽水 | 不接 LLM |

## 10. 安全与合规

- 用户聊天/记忆/注单不发免费模型；必要时应脱敏并走不训练数据的付费档。
- Prompt injection：用户文本只放 user role；事实包用结构化 JSON；不让 LLM 调工具/访问网络。
- 日志脱敏：Authorization、Key、手机号/邮箱、注单金额不入日志。
- Provider 数据条款/数据地域/是否训练要先审；免费档不作为长期唯一依赖。
- `match_analysis` 输出必须经数字白名单、禁用词、概率语法；不合格回模板。
- 预算/路由/情报发布必须有审计；RBAC 已落地（viewer/operator/admin），后台写操作须 CSRF + 审计；模型用量页当前仍只读，路由/预算编辑待做。

## 11. 分阶段落地

**Phase 0（先不接 LLM）**
- `/chat` 加 intent/fallback 埋点、匿名/设备限流、20 次/小时配额。
- 统计 fallback 比例；如果很低，不急着接聊天 LLM。

**Phase 1（fast only）— ✅ 已实现**
- `llm_usage` + `llm_cache` + `llm_budgets` + Gateway + fast profile。
- 已接 `open_chat` fallback；`copy_polish` 仍走模板（待接）；固定 intent 0 LLM。
- `/admin` 模型用量页只读 profile/用量/预算/最近调用；启停/熔断开关未做。
- 无 Key/超预算/超时/schema 失败 → `degraded`，调用方保留固定引导。

**Phase 2（deep analysis）— 待做**
- `intel_items`/`match_coverage`/`analysis_jobs`/`ai_analyses`。
- DeepSeek 只对 eligible 场次异步生成；focus 读缓存；后台审核/发布。
- 一份分析 + 三套人设外壳，不按用户生成。

**Phase 3（多 profile/路由）— 待做**
- `llm_profiles`/`llm_routes` 持久化；备份 profile；A/B/影子。
- RBAC/审计/成本看板；再考虑更多 provider。

## 12. 测试矩阵

| 用例 | 期望 |
|---|---|
| 500 并发预算预占 | 不超过 `llm_budgets.limit_cny`，无负余额 |
| provider 429/5xx | 只重试 1 次；仍失败 → fallback/模板 |
| provider 超时 | 不重试；熔断计数 +1 |
| schema 校验失败 | 最多重试 1 次；再失败 → 模板，不写缓存 |
| 数字白名单 | 未授权数字/单位/百分比 → 拒绝，模板 |
| prompt injection | 用户文本不能改变系统规则/调用工具 |
| 缓存命中 | `data_cutoff/prompt_ver/model` 任一变化则 miss |
| 用户私有缓存 | 不允许跨 user 命中 |
| 免费模型 PII | 手机号/注单/记忆不出现在请求 |
| deep 资格 | `deep_eligible=false` 不入队 |
| 重复任务 | 同 `input_hash` 只生成一次 |
| 管理后台改路由 | 写 `admin_audit`，可回滚 |
| Key 泄漏 | API/日志/HTML 不出现明文 Key |

## 13. 验收

- 固定意图 0 LLM；fallback 才进 fast；深读只进 deep 且数据达标。
- 预算并发测试不超支；超时/429/schema 失败均有模板。
- 缓存 key 包含 data_cutoff/prompt_ver/provider/model；数据更新失效。
- 输出无未授权数字/禁用词/预测承诺。
- Key 不出现在 API 响应、日志、控制台 HTML。
- 新增路由重新采纳 W8 freeze 基线；迁移可 up/down。
