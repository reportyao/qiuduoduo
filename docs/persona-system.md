# 人设与文案配置（三种语气，同一事实）

> 状态：**部分实现。** 2026-11-05：模型池/加密 Key/后台配置/failover/缓存/预生成 CLI、narration 缓存、persona_profiles/persona_copy_slots 与 `GET /personas` 已落地；copy slots 目前只建表/可编辑，运行时尚未消费；模型 HTTP 调用已统一走 `llm_gateway.call_profile`。AI 复核已接入推荐主链（L1–L5），recommendation_copies、前端服务端文案切换仍待开发。
>
> 目标：`zhuanjia` / `laopao` / `meng` 三种人设只改变**语气与表达**，绝不改变方向、概率、条件、成本、组合腿、复核状态。

## 1. 迁移前的问题（正在消除）

当前人设文案仍有一部分分散在两处：

- 移动端：`apps/mobile/src/features/personas/personas.ts`（`PERSONAS` + `COPY`，大量硬编码 UI 文案）
- 后端：`jieqiu-backend/app/modules/narrate.py`（三套叙述模板）

问题：

- 新增 Today Hero、参考组合、AI 复核徽章、付费墙、空态、复盘、推送后，会变成第三、第四处硬编码。
- 前后端文案容易漂移（同一句“复核中”两种说法）。
- 无法在后台调整语气/称呼/长度，每次改文案都要发版。
- AI 复核无法按人设检查“是否过度承诺/是否偏离人设”。

## 2. 目标架构

### 2.1 为什么用便宜 LLM 做“翻译”

硬编码模板稳定但会重复、生硬；每次请求让 LLM 自由写又会漂移、贵、不可审。

正确做法是：

> **事实由模型/规则生成，语气由便宜 LLM 做“翻译”；只在发布前批量生成，不在用户请求时现写。**

- 当前默认：TokenRhythm `https://tokenrhythm.studio/v1`，模型池 `egg-alpha`（priority 10）→ `neohorse-1-9b`（priority 20）；后台可继续添加其他 OpenAI-compatible 模型。
- 每种 persona 一次调用，输出一段人设文案（不是结构化槽位）；同一 draft 缓存。
- 数字/方向/条件用占位符锁定，LLM 不能生成新数字。
- 目标态是翻译结果再交给 deep/异家族 reviewer 复核；当前尚未接 reviewer，失败回退模板。

### 2.2 生成时机

```text
draft 通过事实/规则检查
  → python -m app.persona_cli warm --date YYYY-MM-DD
  → 对 zhuanjia/laopao/meng 各调用一次 fast LLM
  → 每个 persona 独立复核（待接）
  → 通过：写入 persona_copy_cache（recommendation_copies 待建）
  → 失败：当前直接走 narrate.py 模板（copy slots 的运行时回退待接）

用户请求 /verdicts/{id}/narration.stream 只读 persona_copy_cache；
缓存未命中走 narrate.py 模板，不同步等 LLM。
```

不在 `/recommendations/today` 请求时调用 LLM；前端只读已生成文案。

```text
canonical facts（方向/概率/条件/成本/腿）
        ↓
persona translator（便宜 fast LLM，发布前批量翻译）
        ↓
persona reviewer（deep/异家族模型 + 规则，事实/人设/表达）
        ↓
recommendation_copies（每个 persona 一份，缓存）
        ↓
mobile GET /personas + 用户 persona
```

### 单一事实源

所有数字、方向、条件、组合腿来自 `decision_snapshots` / `recommendation_plans` 的 canonical payload。人设层只能引用占位符，不能生成新数字。

## 3. 数据表（部分实现）

```text
persona_profiles
  id: zhuanjia|laopao|meng
  name, address, tone_summary
  system_prompt, few_shot_json
  max_chars, emoji_policy, allowed_emoji
  banned_phrases_json
  version, enabled, updated_at

persona_copy_slots
  persona_id, slot_key, template_text, version, enabled
  slot_key: today_pick / plan_intro / plan_why_not / conditions /
            review_badge / paywall / empty / postmatch / push / share

recommendation_copies
  draft_id, persona_id, text, review_status,
  review_run_id, prompt_ver, created_at
```

`persona_copy_slots` 已建表并可后台编辑，目标是作为 LLM 失败时的兜底模板；当前运行时尚未消费，实际回退仍是 `narrate.py` 的 `TEMPLATES`。`recommendation_copies` 尚未建表。

## 4. API（部分实现）

```text
GET  /personas                  返回 profile + copy slots + version（✅ 已实现；移动端尚未消费）
GET  /admin/api/personas         后台读取 profile + slots（页面：/admin 人设文案）
PUT  /admin/api/personas/{id}    改 profile（admin）
PUT  /admin/api/personas/{id}/slots/{slot}  改槽位（admin）
POST /admin/api/persona/test     人设翻译测试（operator）
```

移动端当前仍使用 bundled `COPY`；服务端版本更新后的异步刷新待接入。

## 5. 三种人设的语气矩阵

| 维度 | zhuanjia 理性专家 | laopao 感性老炮 | meng 萌妹 |
|---|---|---|---|
| 称呼 | 你 | 兄弟 | 主人 |
| 句长 | 短、结论先行 | 中短、口语 | 短、语气词 |
| 情绪 | 冷静 | 有情绪但不煽动 | 亲近、勤快 |
| 幽默 | 少 | 有，自嘲/损友感 | 轻，少量颜文字 |
| Emoji | 不用 | 少量 | 可用 ♡ / ～ |
| 风险表达 | “条件不成立就撤” | “别上头，账算明白” | “人家会马上改口” |
| 禁止 | 含糊、模棱两可 | 包在我身上/稳了 | 过度承诺/色情化 |
| 数字 | 必须精确 | 可口语化但保留数字 | 可可爱化但保留数字 |

## 6. 文案示例：今日主看

### zhuanjia

> 今日主看：曼城 vs 利物浦。  
> 倾向：主队方向。把握度：中。  
> 因为：主场强度 + 对手中卫缺阵。  
> 除非：曼城两名主力轮换，或盘口跌破 1.65。

### laopao

> 兄弟，今天先看这场：曼城 vs 利物浦。  
> 我倾向主队方向，把握度中。  
> 主场硬，对面中卫还缺人；但瓜帅要是大轮换，这判断就得收。

### meng

> 主人～今天人家最想让主人看这场：曼城 vs 利物浦。  
> 人家倾向主队方向，把握度中哦。  
> 因为主场强度高、对面中卫缺阵；但如果主队轮换，人家会马上改口嘛。

三版必须同时保留：主队方向、把握度中、主场强度、对手中卫缺阵、轮换失效条件。

## 7. 文案示例：参考组合

### zhuanjia

> 参考组合：2 串 1，成本 21.4 元，把握度中。  
> 不建议加到 3 串 1：多一腿成本 +8.4 元，第三腿同联赛同时段，相关性上升。

### laopao

> 兄弟，今天就配个 2 串 1，别贪 3 串 1。  
> 多一腿多花 8 块 4，第三腿还跟前面撞联赛，不划算。

### meng

> 主人～人家只配了一个 2 串 1 哦，3 串 1 今天不划算嘛。  
> 多一腿要多花 8.4 元，还容易撞车，人家不想让主人多花冤枉钱。

## 7.5 翻译输出协议

LLM 只输出槽位，不输出最终数字：

```json
{
  "headline": "今天先看这场：[[home]] vs [[away]]",
  "body": "我倾向[[direction]]，把握度[[confidence]]。因为：[[reason]]。",
  "risk": "除非：[[invalidator]]。",
  "cta": "看组合"
}
```

规则：

- `[[direction]]`、`[[confidence]]`、`[[reason]]`、`[[invalidator]]`、`[[cost]]` 等占位符必须原样保留。
- 渲染器最后注入 canonical 值；LLM 输出里出现未授权数字直接 reject。
- 每个 persona 的 profile 提供称呼、句长、emoji、禁用短语、few-shot。
- 输出 JSON schema 校验；不合法重试 1 次。

## 8. AI 复核规则（按人设）

每个 persona 的文案都要过：

1. **事实不变**：方向/概率区间/条件/成本/腿数必须与 canonical payload 一致。
2. **人设匹配**：称呼、句长、emoji 策略符合 profile。
3. **不过度承诺**：
   - zhuanjia 不出现“确定/必然”；
   - laopao 不出现“包在我身上/稳了”；
   - meng 不出现“人家保证/一定”。
4. **方向清楚**：不能为了可爱/幽默把“主队方向”说成“随便看看”。
5. **风险清楚**：必须保留至少一条失效条件。
6. **数字白名单**：文案中的每个数字必须能在 canonical payload 找到。

复核失败：

- 只重写该 persona 的文案；
- 重写 2 次仍失败 → 目标回退到 `persona_copy_slots`（运行时接入待做）；当前回退到 `narrate.py` 模板；
- 模板也失败 → 该 persona 不展示推荐，只展示数据卡。

## 8.5 人设稳定性指标

- 称呼命中率（你/兄弟/主人）
- 平均句长、emoji 数量
- 禁用短语命中
- 数字/方向/条件与 canonical 一致率
- 同一 draft 三次生成的人设相似度
- 用户对三种语气的偏好/A/B

这些指标由 reviewer 自动计算，不靠人工。

## 9. 后台配置（已实现首版）

`/admin` 人设文案页：

- 模型池列表：名称 / Base URL / model / 优先级 / 启用 / Key 状态 / 失败次数 / 最近错误
- 添加模型：name、base_url、model、api_key、priority、max_tokens、temperature
- 启用/停用/删除；每行可直接更新 Key（轮换不需要删模型重建）
- 翻译测试：选 persona + 输入中性事实文本，返回实际模型/延迟/文案
- Key 使用 Fernet 加密落库，页面只显示“已配置/未配置”
- 写操作依赖 HttpOnly cookie 会话，已接入 `admin_audit` 与 CSRF 校验；角色/启停/改密/删除会撤销会话

CLI：

```bash
python -m app.persona_cli models
python -m app.persona_cli test --persona laopao --text "..."
python -m app.persona_cli warm --date 2026-11-05
```

`persona_llm_models` / `persona_copy_cache` 表已落迁移 `20261104_08`；`persona_profiles` / `persona_copy_slots` 表已落迁移 `20261104_09`。

## 9.1 后台配置（后续）

`/admin` 人设文案页（后续）：

- 三种人设的称呼、语气、长度、emoji、禁用短语
- 每个 slot 的模板
- few-shot 示例
- 用真实 draft 预览三种文案
- 版本发布/回滚
- 查看 AI 复核通过率/重写率

## 10. 迁移步骤

1. 保留 `personas.ts` / `narrate.py` 作为 bundled fallback。
2. 新增 `persona_profiles` / `persona_copy_slots`，导入当前三套文案。
3. 新增 `GET /personas`，移动端优先读服务端，失败回退 bundled。
4. `narrate.py` 改为读 profile + slot，不再硬编码。
5. 新增 `recommendation_copies`，每个 draft 生成三份文案并分别复核。
6. 后台 `/admin` 人设文案页验证稳定后再移除硬编码。

## 11. 验收

- 三种人设的方向/概率/条件/成本完全一致。
- 同一 draft 的三份文案都通过 AI 复核才发布。
- 任一 persona 文案失败，不影响其他 persona；失败 persona 回退模板。
- 修改文案配置不需要发版。
- 人设切换后，Today Hero、组合卡、付费墙、空态、复盘、推送全部换语气，但数字不变。
