const state = {
  view: "overview",
  date: "",
  recommendationFilter: "all",
  recommendationQuery: "",
  recoLimit: 50,
  recoOffset: 0,
  recoItems: [],
  logName: "sync",
  modelEvalDays: 90,
  autoRefresh: true,
  role: "",
  auditOffset: 0,
  cache: {},
};

const canOperate = () => ["operator", "admin"].includes(state.role);
const canAdmin = () => state.role === "admin";

const el = (sel) => document.querySelector(sel);
const els = (sel) => [...document.querySelectorAll(sel)];
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
}[c]));
const num = (value, digits = 0) => Number(value ?? 0).toFixed(digits);
const fmtTime = (value, seconds = false) => {
  const text = String(value || "");
  if (!text) return "—";
  const match = text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::(\d{2}))?/);
  if (!match) return text;
  return `${match[1]} ${match[2]}${seconds && match[3] ? `:${match[3]}` : ""}`;
};

function toast(message, type = "success", ms = 3200) {
  const box = el("#toast");
  box.textContent = message;
  box.className = `toast show ${type}`;
  clearTimeout(box._timer);
  box._timer = setTimeout(() => box.classList.remove("show"), ms);
}

function csrfToken() {
  const match = document.cookie.split("; ").find(item => item.startsWith("admin_csrf="));
  return match ? decodeURIComponent(match.slice("admin_csrf=".length)) : "";
}

function ensureCsrf(session) {
  if (!csrfToken() && session && session.csrf_token) {
    document.cookie = `admin_csrf=${encodeURIComponent(session.csrf_token)}; path=/; samesite=strict`;
  }
}

async function api(path, options = {}) {
  const headers = {};
  if (options.body) headers["Content-Type"] = "application/json";
  const token = csrfToken();
  if (token) headers["X-CSRF-Token"] = token;
  const response = await fetch(path, {
    credentials: "same-origin",
    headers,
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (response.status === 401) {
    showLogin();
    throw new Error("需要控制台登录");
  }
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { detail: text }; }
  if (!response.ok) throw new Error(data.detail || data.error || `请求失败（${response.status}）`);
  return data;
}

async function post(path, body = {}) {
  return api(path, { method: "POST", body });
}
async function put(path, body = {}) {
  return api(path, { method: "PUT", body });
}
async function patch(path, body = {}) {
  return api(path, { method: "PATCH", body });
}
async function del(path) {
  return api(path, { method: "DELETE" });
}

function showLogin() {
  el("#app").hidden = true;
  el("#login").style.display = "grid";
}

function showApp() {
  el("#login").style.display = "none";
  el("#app").hidden = false;
}

function applyRole() {
  els("[data-admin-only]").forEach(item => {
    item.style.display = canAdmin() ? "" : "none";
  });
}

function statusPill(status) {
  const map = {
    published: ["green", "已发布"], approved: ["blue", "已过审"],
    promoted: ["green", "已过三关"], screening: ["amber", "复核中"],
    killed: ["red", "已砍"], ready: ["green", "就绪"],
    unavailable: ["amber", "不可用"],
    review_failed: ["red", "复核失败"], reviewing: ["amber", "复核中"],
    draft: ["amber", "草稿"], expired: ["muted", "已过期"],
    withdrawn: ["muted", "已撤回"], pass: ["green", "通过"],
    fail: ["red", "失败"], skip: ["amber", "跳过"],
    ok: ["green", "正常"], degraded: ["red", "降级"],
    cached: ["blue", "缓存"], blocked: ["amber", "拦截"],
  };
  const [cls, label] = map[status] || ["muted", status || "—"];
  return `<span class="pill ${cls}">${esc(label)}</span>`;
}

function gatePills(gates = {}) {
  const names = { price: "价", market: "市", model: "模" };
  const labels = { pass: "过", fail: "败", pending_data: "待" };
  return `<span class="gate-row">${["price", "market", "model"].map(key => {
    const value = gates[key];
    const cls = value === "pass" ? "pass" : value === "fail" ? "fail" : value === "pending_data" ? "pending" : "";
    return `<span class="gate ${cls}"><span class="gate-key">${names[key]}</span><span class="gate-val">${esc(labels[value] || "—")}</span></span>`;
  }).join("")}</span>`;
}

function skeleton(count = 3) {
  return Array.from({ length: count }, () => '<div class="skeleton"></div>').join("");
}

function modal(title, html) {
  el("#modal-card").innerHTML = `<h3>${esc(title)}</h3>${html}`;
  el("#modal").hidden = false;
}
function closeModal() {
  el("#modal").hidden = true;
  el("#modal-card").innerHTML = "";
}

function confirmModal(title, message, action) {
  modal(title, `
    <p style="margin:0 0 20px;color:var(--ink-2)">${esc(message)}</p>
    <div class="actions">
      <button class="btn primary" id="confirm-action">确认执行</button>
      <button class="btn ghost" id="cancel-action">取消</button>
    </div>
  `);
  el("#confirm-action").onclick = async () => {
    try {
      await action();
      closeModal();
    } catch (error) {
      toast(error.message, "error");
    }
  };
  el("#cancel-action").onclick = closeModal;
}

/* ---------- overview ---------- */

async function loadOverview() {
  const root = el("#view-overview");
  root.innerHTML = `<div class="kpi-grid">${skeleton(4)}</div>`;
  const data = await api("/admin/api/overview");
  state.cache.overview = data;
  const c = data.counts;
  const gatewayRows = data.gateway.rows || [];
  const totalCost = gatewayRows.reduce((sum, row) => sum + Number(row.cost_cny || 0), 0);
  const totalCalls = gatewayRows.reduce((sum, row) => sum + Number(row.calls || 0), 0);
  const published = (c.snapshots.published || 0) + (c.plans.published || 0);
  const healthyModels = Math.max(0, c.models.enabled - c.models.degraded);
  const stageCount = key => (c.snapshots[key] || 0) + (c.plans[key] || 0);
  const stages = [
    ["draft", "草稿"],
    ["reviewing", "复核中"],
    ["approved", "已过审"],
    ["published", "已发布"],
  ];
  const reviewFailed = stageCount("review_failed");
  root.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi green accent"><div class="kpi-label">今日过三关</div><div class="kpi-value">${c.verdicts_today.promoted}</div><div class="kpi-foot">复核中 ${c.verdicts_today.screening} · 已砍 ${c.verdicts_today.killed}</div></div>
      <div class="kpi"><div class="kpi-label">今日已发布</div><div class="kpi-value">${published}</div><div class="kpi-foot">snapshot ${c.snapshots.published || 0} · plan ${c.plans.published || 0}</div></div>
      <div class="kpi ${c.models.degraded ? "amber" : "green"}"><div class="kpi-label">模型池健康</div><div class="kpi-value">${healthyModels}/${c.models.total}</div><div class="kpi-foot">降级 ${c.models.degraded} · 未配 Key ${c.models.total - c.models.configured}</div></div>
      <div class="kpi"><div class="kpi-label">模型调用（今日）</div><div class="kpi-value">${totalCalls}</div><div class="kpi-foot">成本 ¥${num(totalCost, 4)}</div></div>
    </div>

    <div class="card">
      <div class="toolbar">
        <div><h2 style="margin:0">今日待办</h2><div class="card-sub" style="margin:0">只处理会阻塞发布或影响数据的事项</div></div>
        <div class="filters">
          <button class="filter" data-jump="recommendations">推荐主链</button>
          <button class="filter" data-jump="models">模型池</button>
        </div>
      </div>
      ${(data.actions || []).length ? data.actions.map(action => `
        <div class="status-item">
          <div>
            <div style="display:flex;align-items:center;gap:8px"><b>${esc(action.label)}</b>${statusPill(action.severity === "high" ? "fail" : action.severity === "medium" ? "reviewing" : "skip")}</div>
            <div class="status-label" style="margin-top:4px">${esc(action.detail)}</div>
          </div>
          <button class="btn ${action.severity === "high" ? "primary" : "secondary"} small" data-action-view="${esc(action.view)}" data-action-filter="${esc(action.filter || "all")}">去处理</button>
        </div>
      `).join("") : '<div class="empty">没有阻塞项。数据、模型和发布都正常。</div>'}
      <div class="status-item">
        <div><b>SP 数据</b><div class="status-label">最新 ${esc(fmtTime(data.sync?.latest, true))} · lag ${data.sync?.lag_seconds == null ? "—" : data.sync.lag_seconds + "s"}</div></div>
        ${data.sync?.lag_seconds == null ? statusPill("skip") : data.sync.lag_seconds > 1800 ? statusPill("fail") : statusPill("ok")}
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">今日主链</h2>
          <div class="card-sub">从草稿到用户可见，按状态计数</div>
        </div>
        <button class="btn ghost small" data-jump="recommendations">查看全部</button>
      </div>
      <div class="pipeline">
        ${stages.map(([key, label], index) => `
          <button class="pipeline-step ${key}" data-jump="recommendations" data-jump-filter="${key}">
            <span class="pipeline-index">0${index + 1}</span>
            <span class="pipeline-name">${label}</span>
            <span class="pipeline-count">${stageCount(key)}</span>
          </button>
        `).join("")}
      </div>
      <div class="pipeline-meta">
        <span>复核通过 <b>${c.reviews.passed}/${c.reviews.total}</b></span>
        <span>复核失败 <b>${reviewFailed}</b></span>
        <span>当前发布 <b>${published}</b></span>
      </div>
    </div>

    <div class="grid side">
      <div class="card">
        <h2 class="card-title">模型池状态</h2>
        ${data.models.map(m => `
          <div class="status-item">
            <div><b>${esc(m.model)}</b><div class="status-label">P${m.priority} · ${esc(m.key)}</div></div>
            ${m.enabled ? (m.fail_count >= 3 ? statusPill("fail") : statusPill("ok")) : statusPill("muted")}
          </div>
        `).join("") || '<div class="empty">暂无模型</div>'}
        <div class="detail-list" style="margin-top:16px">
          <div><b>最近快照：</b>${esc(fmtTime(data.latest.snapshot_created_at, true))}</div>
          <div><b>最近事件：</b>${esc(fmtTime(data.latest.event_at, true))}</div>
          <div><b>最近判决：</b>${esc(fmtTime(data.latest.verdict_created_at, true))}</div>
        </div>
      </div>

      <div class="card">
        <h2 class="card-title">今日运行</h2>
        <div class="status-grid">
          <div class="status-item"><span class="status-label">环境</span><b class="mono">${esc(data.env || "—")}</b></div>
          <div class="status-item"><span class="status-label">日期</span><b class="mono">${esc(data.date || "—")}</b></div>
          <div class="status-item"><span class="status-label">复核通过</span><b class="mono">${c.reviews.passed}/${c.reviews.total}</b></div>
          <div class="status-item"><span class="status-label">复核失败</span><b class="mono">${c.reviews.failed || 0}</b></div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2 class="card-title">模型调用（今日）</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>任务</th><th>配置</th><th class="num">调用</th><th class="num">缓存</th><th class="num">Tokens</th><th class="num">成本</th></tr></thead>
        <tbody>${gatewayRows.map(row => `
          <tr><td>${esc(row.task)}</td><td>${esc(row.profile)}</td><td class="num">${row.calls}</td><td class="num">${row.cache_hits}</td><td class="num">${row.input_tokens}/${row.output_tokens}</td><td class="num">¥${num(row.cost_cny, 5)}</td></tr>
        `).join("") || '<tr><td colspan="6">今日无调用</td></tr>'}</tbody>
      </table></div>
    </div>
  `;

  els("[data-action-view]").forEach(btn => btn.onclick = () => {
    state.recommendationFilter = btn.dataset.actionFilter || "all";
    showView(btn.dataset.actionView);
  });
  els("[data-jump]").forEach(btn => btn.onclick = () => {
    if (btn.dataset.jumpFilter) state.recommendationFilter = btn.dataset.jumpFilter;
    showView(btn.dataset.jump);
  });
}

/* ---------- model pool ---------- */

async function loadModels() {
  const root = el("#view-models");
  root.innerHTML = '<div class="card"><div class="skeleton" style="height:80px"></div></div>';
  const data = await api("/admin/api/models");
  root.innerHTML = `
    <div class="card notice" style="margin-bottom:16px"><b>这里是“人设文案”专用模型池</b><div class="card-sub" style="margin-top:6px">只用于三套语气改写（每日 19:05 预生成）；不服务 /chat，也不服务发布前复核。对话与复核请到「接入中心」配置 fast/deep。</div></div>
    <div class="toolbar">
      <div><h2 style="margin:0">文案模型列表</h2><div class="card-sub" style="margin:0">按优先级自动 failover；Key 加密存储，界面只显示配置状态。</div></div>
      ${canAdmin() ? '<button class="btn primary" id="add-model">添加模型</button>' : ''}
    </div>
    <div class="card">${data.models.map(model => `
      <div class="model-row">
        <div>
          <div class="model-title">
            ${esc(model.model)}
            ${model.enabled ? statusPill(model.fail_count >= 3 ? "fail" : "ok") : statusPill("muted")}
            <span class="pill ${model.key === "已配置" ? "green" : "amber"}">${esc(model.key)}</span>
          </div>
          <div class="model-meta">
            <div><b>名称</b> ${esc(model.name)}</div>
            <div><b>接口地址</b> <span class="mono">${esc(model.base_url)}</span></div>
            <div><b>优先级</b> ${model.priority}</div>
            <div><b>最大 Token</b> ${model.max_tokens}</div>
            <div><b>温度</b> ${model.temperature}</div>
            <div><b>超时</b> ${model.timeout_s}s</div>
            <div><b>最近成功</b> ${esc(fmtTime(model.last_ok_at, true))}</div>
            <div><b>失败次数</b> ${model.fail_count}</div>
          </div>
          ${model.last_error ? `<div class="model-error"><b>最近错误</b> · ${esc(model.last_error)}</div>` : ""}
        </div>
        <div class="actions model-actions">
          ${canOperate() ? `<button class="btn secondary small" data-model-test="${model.id}">测试</button>` : ""}
          ${canAdmin() ? `<button class="btn secondary small" data-model-edit="${model.id}">编辑</button>
          <button class="btn secondary small" data-model-key="${model.id}">更新 Key</button>
          <button class="btn ${model.enabled ? "warn" : "primary"} small" data-model-toggle="${model.id}">${model.enabled ? "停用" : "启用"}</button>
          <button class="btn danger small" data-model-delete="${model.id}">删除</button>` : ""}
        </div>
      </div>
    `).join("") || '<div class="empty">暂无模型</div>'}</div>
  `;
  if (el("#add-model")) el("#add-model").onclick = () => openModelModal();
  els("[data-model-toggle]").forEach(btn => btn.onclick = async () => {
    const id = btn.dataset.modelToggle;
    const row = data.models.find(m => String(m.id) === id);
    await patch(`/admin/api/models/${id}`, { enabled: !row.enabled });
    toast(row.enabled ? "模型已停用" : "模型已启用");
    loadModels();
  });
  els("[data-model-delete]").forEach(btn => btn.onclick = () => confirmModal("删除模型", "删除后不可恢复，确认继续？", async () => {
    await del(`/admin/api/models/${btn.dataset.modelDelete}`);
    toast("模型已删除");
    loadModels();
  }));
  els("[data-model-key]").forEach(btn => btn.onclick = () => openKeyModal(Number(btn.dataset.modelKey)));
  els("[data-model-edit]").forEach(btn => btn.onclick = () => openModelModal(data.models.find(m => String(m.id) === btn.dataset.modelEdit)));
  els("[data-model-test]").forEach(btn => btn.onclick = async () => {
    const id = Number(btn.dataset.modelTest);
    btn.disabled = true; btn.textContent = "测试中…";
    try {
      const result = await post(`/admin/api/models/${id}/test`, { persona: "laopao", text: "今天主看曼城，方向主胜，把握度56%，抽水12.1%。" });
      modal("模型测试", result.ok ? `
        <div class="detail-list"><div><b>模型</b> ${esc(result.model)}</div><div><b>延迟</b> ${result.latency_ms}ms</div><div><b>persona</b> ${esc(result.persona)}</div></div>
        <div class="card" style="margin-top:16px;white-space:pre-wrap">${esc(result.text)}</div>
      ` : `<div class="model-error">${esc(result.error)}</div>`);
    } catch (error) {
      toast(error.message, "error");
    }
    btn.disabled = false; btn.textContent = "测试";
    loadModels();
  });
}

function openModelModal(model = null) {
  modal(model ? `编辑模型：${model.model}` : "添加模型", `
    <form id="model-form" class="form-grid">
      <div><label>显示名称</label><input id="mf-name" value="${esc(model?.name || "")}" placeholder="Egg Alpha"></div>
      <div><label>模型 ID</label><input id="mf-model" value="${esc(model?.model || "")}" placeholder="egg-alpha" ${model ? "" : "required"}></div>
      <div class="full"><label>Base URL</label><input id="mf-base" value="${esc(model?.base_url || "https://tokenrhythm.studio/v1")}" placeholder="https://..."></div>
      ${model ? "" : '<div class="full"><label>API Key</label><input id="mf-key" type="password" placeholder="sk_t..."></div>'}
      <div><label>优先级</label><input id="mf-priority" type="number" min="1" value="${model?.priority || 100}"></div>
      <div><label>启用</label><select id="mf-enabled"><option value="true" ${!model || model.enabled ? "selected" : ""}>启用</option><option value="false" ${model && !model.enabled ? "selected" : ""}>停用</option></select></div>
      <div><label>timeout</label><input id="mf-timeout" type="number" min="3" max="120" value="${model?.timeout_s || 20}"></div>
      <div><label>max_tokens</label><input id="mf-tokens" type="number" min="64" max="4096" value="${model?.max_tokens || 800}"></div>
      <div><label>temperature</label><input id="mf-temp" type="number" min="0" max="1.5" step="0.05" value="${model?.temperature || 0.4}"></div>
      <div class="actions full"><button class="btn primary" type="submit">保存</button><button class="btn ghost" type="button" id="mf-cancel">取消</button></div>
    </form>
  `);
  el("#mf-cancel").onclick = closeModal;
  el("#model-form").onsubmit = async (event) => {
    event.preventDefault();
    const body = {
      name: el("#mf-name").value,
      base_url: el("#mf-base").value,
      model: el("#mf-model").value,
      priority: Number(el("#mf-priority").value),
      enabled: el("#mf-enabled").value === "true",
      timeout_s: Number(el("#mf-timeout").value),
      max_tokens: Number(el("#mf-tokens").value),
      temperature: Number(el("#mf-temp").value),
    };
    try {
      if (model) await patch(`/admin/api/models/${model.id}`, body);
      else await post("/admin/api/models", { ...body, api_key: el("#mf-key").value });
      closeModal(); toast("模型已保存"); loadModels();
    } catch (error) { toast(error.message, "error"); }
  };
}

function openKeyModal(id) {
  modal("更新模型 Key", `
    <form id="key-form" class="form-grid"><div class="full"><label>新 API Key</label><input id="new-key" type="password" required></div>
    <div class="actions full"><button class="btn primary" type="submit">更新</button><button class="btn ghost" type="button" id="key-cancel">取消</button></div></form>
  `);
  el("#key-cancel").onclick = closeModal;
  el("#key-form").onsubmit = async event => {
    event.preventDefault();
    await post(`/admin/api/models/${id}/key`, { api_key: el("#new-key").value });
    closeModal(); toast("Key 已更新"); loadModels();
  };
}

/* ---------- personas ---------- */

async function loadPersonas() {
  const root = el("#view-personas");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api("/admin/api/personas");
  root.innerHTML = `
    <div class="grid side">
      <div class="card persona-card">
        <h2 class="card-title">人设配置</h2>
        <div class="card-sub">只控制语气表达，不改变方向、概率、条件与成本。</div>
        ${data.profiles.map(profile => `
          <form class="form-grid" data-profile-form="${esc(profile.id)}" style="padding-top:16px;border-top:1px solid var(--line);margin-top:16px">
            <div><label>名称</label><input name="name" value="${esc(profile.name)}"></div>
            <div><label>称呼</label><input name="address" value="${esc(profile.address)}"></div>
            <div><label>语气标签</label><input name="tone" value="${esc(profile.tone)}"></div>
            <div><label>最大字数</label><input name="max_chars" type="number" min="60" max="600" value="${profile.max_chars}"></div>
            <div><label>表情策略</label><select name="emoji_policy">
              ${[["none", "关闭"], ["limited", "少量"], ["free", "自由"]].map(([x, label]) => `<option value="${x}" ${profile.emoji_policy === x ? "selected" : ""}>${label}</option>`).join("")}
            </select></div>
            <div><label>允许表情</label><input name="allowed_emoji" value="${esc(profile.allowed_emoji)}"></div>
            <div class="full"><label>风格提示</label><textarea name="style_prompt">${esc(profile.style_prompt)}</textarea></div>
            <div class="actions full"><button class="btn primary">保存人设</button><span class="pill muted">v${profile.version}</span></div>
          </form>
        `).join("")}
      </div>
      <div class="card">
        <h2 class="card-title">文案槽位</h2>
        <div class="card-sub">3 个人设不变；每人设 ${data.slot_keys.length} 个槽位，控制前端可见文案与叙述兜底。只改语气，不改数字。</div>
        <div id="slot-editor">${renderSlot(data)}</div>
      </div>
    </div>
    <div class="card">
      <h2 class="card-title">人设翻译测试</h2>
      <form id="persona-test" class="form-grid">
        <div><label>人设</label><select id="pt-persona">${data.profiles.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select></div>
        <div class="full"><label>中性事实文本</label><textarea id="pt-text" placeholder="今天主看曼城，方向主胜，把握度56%，抽水12.1%。"></textarea></div>
        <div class="actions full"><button class="btn primary" type="submit">调用测试</button></div>
      </form>
      <div id="persona-test-result"></div>
    </div>
  `;

  els("[data-profile-form]").forEach(form => form.onsubmit = async event => {
    event.preventDefault();
    const fd = new FormData(form);
    const id = form.dataset.profileForm;
    await put(`/admin/api/personas/${id}`, Object.fromEntries(fd.entries()));
    toast("Profile 已保存"); loadPersonas();
  });

  const slotSelect = el("#slot-persona");
  if (slotSelect) {
    slotSelect.onchange = () => {
      const key = el("#slot-key").value;
      const slot = data.slots.find(s => s.persona_id === slotSelect.value && s.slot_key === key)
        || data.slots.find(s => s.persona_id === slotSelect.value);
      el("#slot-template").value = slot ? slot.template : "";
    };
    slotSelect.dispatchEvent(new Event("change"));
  }
  el("#slot-form").onsubmit = async event => {
    event.preventDefault();
    await put(`/admin/api/personas/${el("#slot-persona").value}/slots/${el("#slot-key").value}`, {
      template: el("#slot-template").value, enabled: true,
    });
    toast("槽位已保存"); loadPersonas();
  };

  el("#persona-test").onsubmit = async event => {
    event.preventDefault();
    const box = el("#persona-test-result");
    box.innerHTML = '<div class="skeleton" style="height:80px"></div>';
    const result = await post("/admin/api/persona/test", {
      persona: el("#pt-persona").value, text: el("#pt-text").value,
    });
    box.innerHTML = result.ok ? `
      <div class="card" style="margin-top:16px">
        <div class="detail-list"><div><b>模型</b> ${esc(result.model)}</div><div><b>延迟</b> ${result.latency_ms}ms</div></div>
        <p style="white-space:pre-wrap;margin-bottom:0">${esc(result.text)}</p>
      </div>
    ` : `<div class="model-error" style="margin-top:16px">${esc(result.error)}</div>`;
  };

  if (!canAdmin()) {
    els("[data-profile-form] input, [data-profile-form] textarea, [data-profile-form] select, #slot-form input, #slot-form textarea, #slot-form select")
      .forEach(item => { item.disabled = true; });
    els("[data-profile-form] button, #slot-form button").forEach(item => item.remove());
  }
  if (!canOperate()) {
    els("#persona-test input, #persona-test textarea, #persona-test select, #persona-test button")
      .forEach(item => { item.disabled = true; });
  }
}

const SLOT_LABELS = {
  brandSub: "品牌副标题",
  saleTitle: "最近停售标题",
  parlayTitle: "串关标题",
  parlaySub: "串关副标题",
  parlayCta: "串关按钮",
  typing: "生成中提示",
  emptyTitle: "空态标题",
  emptyBody: "空态正文",
  restTitle: "休息日标题",
  restBody: "休息日正文",
  chatGreeting: "聊天问候",
  whyNotLead: "为什么不出",
  narration_promoted: "已发布叙述",
  narration_screening: "复核中叙述",
  narration_killed: "被砍叙述",
  today_pick: "今日主看",
  plan_intro: "组合开场",
  plan_why_not: "组合劝退",
  locked: "锁定提示",
  paywall: "付费墙",
  empty: "空态兜底",
  postmatch: "赛后复盘",
  review_badge: "复核徽章",
  push: "推送文案",
};

function renderSlot(data) {
  return `
    <form id="slot-form" class="form-grid">
      <div><label>人设</label><select id="slot-persona">${data.profiles.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select></div>
      <div><label>槽位</label><select id="slot-key">${data.slot_keys.map(k => `<option value="${esc(k)}">${esc((SLOT_LABELS[k] || k) + " · " + k)}</option>`).join("")}</select></div>
      <div class="full"><label>兜底模板</label><textarea id="slot-template"></textarea></div>
      <div class="actions full"><button class="btn primary">保存槽位</button></div>
    </form>
  `;
}

/* ---------- recommendations ---------- */

async function loadRecommendations(append = false) {
  const root = el("#view-recommendations");
  if (!append) root.innerHTML = '<div class="skeleton"></div>';
  const offset = append ? state.recoOffset : 0;
  const data = await api(`/admin/api/recommendations?date=${encodeURIComponent(state.date)}&limit=${state.recoLimit}&offset=${offset}`);
  if (append) {
    data.snapshots = [...state.recoItems, ...data.snapshots];
    data.counts.snapshots = data.page.total;
  }
  state.recoItems = data.snapshots;
  state.recoOffset = data.page.next_offset;
  state.cache.recommendations = data;
  const query = state.recommendationQuery.trim().toLowerCase();
  const filtered = data.snapshots.filter(x =>
    (state.recommendationFilter === "all" || x.status === state.recommendationFilter)
    && (!query || [x.home, x.away, x.match_no, x.league, x.direction]
      .join(" ").toLowerCase().includes(query))
  );
  const counts = data.counts;
  const filterLabels = {
    all: "全部", draft: "草稿", reviewing: "复核中", approved: "已过审",
    review_failed: "复核失败", published: "已发布", expired: "已过期",
    withdrawn: "已撤回",
  };
  root.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi green accent"><div class="kpi-label">已发布</div><div class="kpi-value">${counts.published}</div><div class="kpi-foot">${esc(data.date)}</div></div>
      <div class="kpi"><div class="kpi-label">Snapshot</div><div class="kpi-value">${counts.snapshots}</div><div class="kpi-foot">含全部版本</div></div>
      <div class="kpi"><div class="kpi-label">Plan</div><div class="kpi-value">${counts.plans}</div><div class="kpi-foot">含全部版本</div></div>
      <div class="kpi ${counts.review_failed ? "red" : "green"}"><div class="kpi-label">复核失败</div><div class="kpi-value">${counts.review_failed}</div><div class="kpi-foot">可重试</div></div>
    </div>

    <div class="card">
      <div class="toolbar reco-toolbar">
        <div class="filters">
          ${Object.entries(filterLabels).map(([value, label]) => `
            <button class="filter ${state.recommendationFilter === value ? "active" : ""}" data-filter="${value}">${label}</button>`).join("")}
        </div>
        <div class="actions">
          <input id="reco-search" type="search" placeholder="搜场次 / 球队" value="${esc(state.recommendationQuery)}">
          <input id="reco-date" type="date" value="${esc(data.date)}">
          ${canOperate() ? `<button class="btn secondary" id="batch-review">全部复核</button>
          <button class="btn secondary" id="batch-publish">发布已过审</button>
          <button class="btn primary" id="run-pipeline">运行主链</button>` : ""}
        </div>
      </div>
      <div id="reco-list">${filtered.length ? filtered.map(recoCard).join("") : '<div class="empty">当前筛选暂无 snapshot</div>'}</div>
      ${data.page?.has_more ? '<div style="text-align:center;margin-top:16px"><button class="btn secondary" id="reco-more">加载更多（已显示 ' + data.snapshots.length + ' / ' + data.page.total + '）</button></div>' : ""}
    </div>

    <div class="grid side">
      <div class="card"><h2 class="card-title">参考组合生命周期</h2>${data.plans.map(plan => `
        <div class="status-item">
          <div style="flex:1"><b>${esc(plan.label)}</b><div class="status-label">v${plan.version} · ${plan.legs.length} 腿</div>
            <div class="actions" style="margin-top:8px">
              <button class="btn secondary small" data-review="${plan.id}">查看复核</button>
              ${canOperate() && (plan.status === "draft" || plan.status === "review_failed") ? `<button class="btn primary small" data-rereview="${plan.id}" data-type="plan">重新复核</button>` : ""}
              ${canOperate() && plan.status === "approved" ? `<button class="btn primary small" data-publish="${plan.id}" data-type="plan">发布</button>` : ""}
              ${canOperate() && ["approved", "published", "review_failed"].includes(plan.status) ? `<button class="btn danger small" data-withdraw="${plan.id}" data-type="plan">撤回</button>` : ""}
            </div>
          </div>
          ${statusPill(plan.status)}
        </div>`).join("") || '<div class="empty">暂无 plan</div>'}</div>
      <div class="card"><h2 class="card-title">最近主链事件</h2><div class="event-list">${data.events.map(e => `
        <div class="event-item"><span class="mono">${esc(fmtTime(e.created_at, true))}</span><span class="pill muted">${esc(e.action)}</span><span class="mono ellipsis">${esc(e.subject_id)}</span><span>${esc(e.note || `${e.from_status || "—"} → ${e.to_status || "—"}`)}</span></div>`).join("") || '<div class="empty">暂无事件</div>'}</div></div>
    </div>
  `;

  els("[data-filter]").forEach(btn => btn.onclick = () => {
    state.recommendationFilter = btn.dataset.filter;
    state.recoOffset = 0;
    loadRecommendations();
  });
  el("#reco-date").onchange = event => {
    state.date = event.target.value; state.recoLimit = 50; state.recoOffset = 0; loadRecommendations();
  };
  const more = el("#reco-more");
  if (more) more.onclick = () => { state.recoLimit = 50; loadRecommendations(true); };
  el("#reco-search").oninput = event => {
    state.recommendationQuery = event.target.value;
    const q = state.recommendationQuery.trim().toLowerCase();
    els("#reco-list .reco-card").forEach(card => {
      card.style.display = !q || (card.dataset.search || "").includes(q) ? "" : "none";
    });
  };
  if (el("#run-pipeline")) el("#run-pipeline").onclick = async () => {
    const btn = el("#run-pipeline"); btn.disabled = true; btn.textContent = "运行中…";
    try {
      const result = await post("/admin/api/recommendations/run", { date: state.date, stake: 100 });
      toast(`主链完成：snapshot ${result.snapshots}，published ${result.published}`, "success", 5000);
      loadRecommendations();
    } catch (error) { toast(error.message, "error"); }
    btn.disabled = false; btn.textContent = "运行主链";
  };
  if (el("#batch-review")) el("#batch-review").onclick = () => confirmModal("批量复核", "复核今日全部 draft/review_failed？LLM 调用可能耗时。", async () => {
    const result = await post("/admin/api/recommendations/batch", { action: "review", date: state.date });
    toast(`批量复核：完成 ${result.done}，跳过 ${result.skipped}，错误 ${result.errors.length}`, result.errors.length ? "warn" : "success", 5000);
    loadRecommendations();
  });
  if (el("#batch-publish")) el("#batch-publish").onclick = () => confirmModal("批量发布", "发布今日全部 approved？", async () => {
    const result = await post("/admin/api/recommendations/batch", { action: "publish", date: state.date });
    toast(`批量发布：完成 ${result.done}，跳过 ${result.skipped}，错误 ${result.errors.length}`, result.errors.length ? "warn" : "success", 5000);
    loadRecommendations();
  });

  bindSubjectButtons(data);
}

function recoCard(item) {
  const title = item.match_no ? `${item.match_no} ${item.home} vs ${item.away}` : item.label;
  const sub = `${item.league || "联赛待同步"} · ${item.kickoff || "时间待同步"} · v${item.version}`;
  const searchText = [item.home, item.away, item.match_no, item.league, item.direction]
    .join(" ").toLowerCase();
  return `
    <div class="reco-card ${item.status}" data-search="${esc(searchText)}">
      <div class="reco-head">
        <div><div class="reco-title">${esc(title)}</div><div class="reco-sub">${esc(sub)} · ${esc(item.direction)}</div></div>
        ${statusPill(item.status)}
      </div>
      <div class="detail-list" style="margin-top:12px">
        <div><b>三关：</b>${gatePills(item.gates)} <b>封存：</b>${item.sealed ? "是" : "否"}</div>
        <div><b>条件：</b>${esc((item.conditions || []).join("；") || "—")}</div>
        <div><b>失效：</b>${esc((item.invalidators || []).join("；") || "—")}</div>
        <div><b>hash：</b><span class="mono">${esc(item.payload_hash.slice(0, 18))}…</span></div>
      </div>
      <div class="actions" style="margin-top:16px">
        <button class="btn secondary small" data-review="${item.id}" data-type="decision">查看复核</button>
        ${canOperate() && (item.status === "draft" || item.status === "review_failed") ? `<button class="btn primary small" data-rereview="${item.id}" data-type="decision">重新复核</button>` : ""}
        ${canOperate() && item.status === "approved" ? `<button class="btn primary small" data-publish="${item.id}" data-type="decision">发布</button>` : ""}
        ${canOperate() && ["approved", "published", "review_failed"].includes(item.status) ? `<button class="btn danger small" data-withdraw="${item.id}" data-type="decision">撤回</button>` : ""}
      </div>
    </div>
  `;
}

function bindSubjectButtons(data) {
  els("[data-review]").forEach(btn => btn.onclick = () => {
    const run = data.reviews[btn.dataset.review];
    if (!run) return toast("暂无复核记录", "warn");
    modal("AI Review 明细", `
      <div class="detail-list"><div><b>状态</b> ${statusPill(run.status)}</div><div><b>reviewer</b> ${esc(run.reviewer)}</div><div><b>prompt</b> ${esc(run.prompt_ver)}</div><div><b>LLM</b> ${run.llm_degraded ? "降级/未调用" : "已调用"}</div></div>
      <div style="margin-top:16px">${(run.layers || []).map(layer => `
        <div class="review-layer"><div class="review-name">${esc(layer.name)}</div>${statusPill(layer.status)}<div style="color:var(--ink-2);font-size:12px"><pre style="white-space:pre-wrap;margin:0;font:inherit">${esc(JSON.stringify(layer.detail ?? layer, null, 2))}</pre></div></div>`).join("")}
      </div>
    `);
  });
  els("[data-rereview]").forEach(btn => btn.onclick = async () => {
    btn.disabled = true; btn.textContent = "复核中…";
    try {
      const result = await post(`/admin/api/recommendations/${btn.dataset.type}/${btn.dataset.rereview}/review`);
      toast(result.review.status === "passed" ? "复核通过" : "复核失败", result.review.status === "passed" ? "success" : "error");
      loadRecommendations();
    } catch (error) { toast(error.message, "error"); btn.disabled = false; btn.textContent = "重新复核"; }
  });
  els("[data-publish]").forEach(btn => btn.onclick = () => confirmModal("发布内容", "确认发布到用户端？", async () => {
    await post(`/admin/api/recommendations/${btn.dataset.type}/${btn.dataset.publish}/publish`);
    toast("已发布"); loadRecommendations();
  }));
  els("[data-withdraw]").forEach(btn => btn.onclick = () => modal("撤回内容", `
    <form id="withdraw-form" class="form-grid"><div class="full"><label>撤回理由</label>
      <textarea id="withdraw-reason" required placeholder="例如：临场盘口反转，判断失效"></textarea></div>
      <div class="actions full"><button class="btn danger" type="submit">确认撤回</button>
      <button class="btn ghost" type="button" id="withdraw-cancel">取消</button></div></form>`));
  // bind once after modal opens: use event delegation on submit
  if (el("#withdraw-form")) el("#withdraw-form").onsubmit = async event => {
    event.preventDefault();
    const reason = el("#withdraw-reason").value.trim();
    if (!reason) return;
    try {
      await post(`/admin/api/recommendations/${btn.dataset.type}/${btn.dataset.withdraw}/withdraw`, { reason });
      closeModal(); toast("已撤回"); loadRecommendations();
    } catch (error) { toast(error.message, "error"); }
  };
  if (el("#withdraw-cancel")) el("#withdraw-cancel").onclick = closeModal;
}

/* ---------- workbench ---------- */

let workbenchData = null;
let workbenchDiag = null;

function wbPill(state) {
  if (state === "ok") return '<span class="pill green">正常</span>';
  if (state === "warn") return '<span class="pill amber">需关注</span>';
  if (state === "idle") return '<span class="pill muted">无场次</span>';
  return '<span class="pill red">卡住</span>';
}

function wbMetric(metric) {
  return `<div class="wb-metric"><span>${esc(metric.label)}</span><b>${esc(metric.value)}</b></div>`;
}

function wbStageCard(stage) {
  const actions = (stage.actions || []).map(id =>
    `<button class="btn ghost small" data-wb-action="${esc(id)}">${esc(wbActionLabel(id))}</button>`).join("");
  const evidence = Array.isArray(stage.evidence)
    ? stage.evidence
    : stage.evidence ? [String(stage.evidence)] : [];
  return `
    <div class="card wb-stage ${esc(stage.state)}">
      <div class="card-head">
        <div><h2 class="card-title">${esc(stage.title)}</h2><div class="card-sub">${esc(stage.question)}</div></div>
        ${wbPill(stage.state)}
      </div>
      <div class="wb-stage-headline">${esc(stage.headline)}</div>
      <div class="wb-metrics">${(stage.metrics || []).map(wbMetric).join("")}</div>
      ${evidence.length ? `<div class="wb-evidence">${evidence.map(e => `<div>· ${esc(e)}</div>`).join("")}</div>` : ""}
      <div class="wb-next"><b>下一步</b> ${esc(stage.next)}</div>
      ${actions ? `<div class="integration-actions">${actions}</div>` : ""}
      <details class="wb-definition"><summary>这是什么？</summary><div>${esc(stage.definition)}</div></details>
    </div>`;
}

function wbActionLabel(id) {
  return ({
    restart_collector: "重启采集器",
    sync_odds: "同步国际盘",
    sync_sportmonks: "同步 Sportmonks",
    sync_intel: "同步 AI 情报",
    test_llm: "测试 LLM",
    run_pipeline: "运行主链",
  })[id] || id;
}

async function wbRunAction(id) {
  const unsafe = ["sync_odds", "sync_sportmonks", "sync_intel", "run_pipeline"].includes(id);
  const run = async () => {
    const body = { action: id };
    if (state.date) body.date = state.date;
    const result = await post("/admin/api/workbench/action", body);
    toast(result.message || (result.ok ? "动作已完成" : "动作未完成"), result.ok ? "success" : "error");
    await loadWorkbench();
  };
  if (!unsafe) return run();
  const prompts = {
    run_pipeline: "会运行 build→复核→发布，可能改变前端内容。确认执行？",
    sync_sportmonks: "会请求 Sportmonks API 并消耗额度，只同步今日竞彩目标场次。确认执行？",
    sync_intel: "会请求 Sportmonks 事实并调用 LLM 生成中文摘要，可能消耗额度。确认执行？",
    sync_odds: "会请求 The Odds API 并消耗额度，只请求竞彩目标场次。确认执行？",
  };
  confirmModal(wbActionLabel(id), prompts[id] || "确认执行？", run);
}

function renderWorkbenchDiagnosis(diagnosis) {
  const box = el("#wb-diagnosis");
  if (!box || !diagnosis) return;
  const causes = (diagnosis.root_causes || []).map(c => `
    <div class="wb-cause"><b>${esc(c.title || c.stage || "")}</b><span>${esc(c.why || "")}</span>
    ${(c.evidence || []).length ? `<div class="card-sub">${c.evidence.map(e => esc(e)).join(" · ")}</div>` : ""}</div>`).join("");
  const actions = (diagnosis.actions || []).map(a => `
    <button class="btn ${a.safe ? "secondary" : "ghost"} small" data-wb-diag-action="${esc(a.id)}">
      ${esc(a.label || wbActionLabel(a.id))}${a.safe ? "" : "（需确认）"}
    </button>`).join("");
  box.innerHTML = `
    <div class="card wb-ai">
      <div class="card-head"><div><h2 class="card-title">AI 诊断</h2>
      <div class="card-sub">${diagnosis.fallback ? "deep 未配置，使用规则诊断" : "基于工作台快照与 LLM"}</div></div>
      <span class="pill ${diagnosis.fallback ? "amber" : "green"}">${diagnosis.fallback ? "规则兜底" : "AI 已分析"}</span></div>
      <div class="wb-ai-headline">${esc(diagnosis.headline || "")}</div>
      ${causes ? `<div class="wb-causes">${causes}</div>` : ""}
      ${diagnosis.needs_human ? `<div class="wb-next"><b>需要你处理</b> ${esc(diagnosis.needs_human)}</div>` : ""}
      ${actions ? `<div class="integration-actions">${actions}
        ${(diagnosis.actions || []).some(a => a.safe) ? '<button class="btn primary small" id="wb-safe-fix">执行安全项</button>' : ""}
      </div>` : ""}
    </div>`;
  els("[data-wb-diag-action]").forEach(btn => btn.onclick = () => wbRunAction(btn.dataset.wbDiagAction));
  if (el("#wb-safe-fix")) el("#wb-safe-fix").onclick = async () => {
    const safe = (diagnosis.actions || []).filter(a => a.safe).map(a => a.id);
    for (const id of safe) {
      try { await post("/admin/api/workbench/action", { action: id, ...(state.date ? { date: state.date } : {}) }); }
      catch (error) { toast(error.message, "error"); }
    }
    toast(safe.length ? "安全项已执行" : "没有可自动执行的安全项");
    await loadWorkbench();
  };
}

async function loadWorkbench() {
  const root = el("#view-workbench");
  root.innerHTML = '<div class="skeleton"></div>';
  const query = state.date ? `?date=${encodeURIComponent(state.date)}` : "";
  const data = await api("/admin/api/workbench" + query);
  workbenchData = data;
  workbenchDiag = null;
  root.innerHTML = `
    <div class="card wb-hero">
      <div class="card-head">
        <div><h2 class="card-title">今日全链路</h2><div class="card-sub">从采集到前端，每一环都给出当前状态、证据和下一步。</div></div>
        ${wbPill(data.overall)}
      </div>
      <div class="wb-headline">${esc(data.headline)}</div>
      <div class="integration-actions">
        <button class="btn primary small" id="wb-ai">AI 体检</button>
        <button class="btn ghost small" id="wb-refresh">刷新</button>
      </div>
    </div>
    <div id="wb-diagnosis"></div>
    <h2 class="section-title">链路</h2>
    <div class="wb-stage-grid">${data.stages.map(wbStageCard).join("")}</div>
    <div class="card"><h2 class="card-title">卡点摘要</h2>
      ${data.blockers.length ? data.blockers.map(b => `<div class="wb-blocker"><b>${esc(b.title)}</b><span>${esc(b.headline)}</span><span class="card-sub">${esc(b.next)}</span></div>`).join("") : '<div class="card-sub">没有 blocked 环节。</div>'}
      ${data.warnings.length ? `<div class="card-sub" style="margin-top:12px">需关注：${data.warnings.map(w => esc(w.title)).join("、")}</div>` : ""}
    </div>
    <details class="card wb-glossary"><summary>名词解释（SP / 主链 / 三闸 / 封存 / 复核 / published）</summary>
      ${Object.entries(data.definitions).map(([k, v]) => `<div class="wb-def"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join("")}
    </details>
  `;
  els("[data-wb-action]").forEach(btn => btn.onclick = () => wbRunAction(btn.dataset.wbAction));
  el("#wb-refresh").onclick = loadWorkbench;
  el("#wb-ai").onclick = async () => {
    const btn = el("#wb-ai"); btn.disabled = true; btn.textContent = "AI 分析中…";
    try {
      const result = await post("/admin/api/workbench/diagnose" + query);
      workbenchDiag = result.diagnosis;
      renderWorkbenchDiagnosis(result.diagnosis);
      toast("AI 体检完成");
    } catch (error) { toast(error.message, "error"); }
    btn.disabled = false; btn.textContent = "AI 体检";
  };
}

/* ---------- collector ---------- */


function ageText(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

async function loadCollector() {
  const root = el("#view-collector");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api("/admin/api/collector");
  const badge = data.state === "online"
    ? '<span class="pill green">在线</span>'
    : data.state === "stale"
      ? '<span class="pill red">离线/超时</span>'
      : '<span class="pill muted">从未上报</span>';
  root.innerHTML = `
    <div class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">家宽采集器</h2>
          <div class="card-sub">采集器每轮上报心跳；服务器无法主动连家庭机器，重启指令由心跳响应下发。</div>
        </div>
        ${badge}
      </div>
      <div class="status-grid" style="margin-top:16px">
        <div class="status-item"><div><b>最后心跳</b><div class="status-label">超过 10 分钟视为离线</div></div><span class="mono">${esc(fmtTime(data.last_seen, true))} · ${ageText(data.stale_seconds)}前</span></div>
        <div class="status-item"><div><b>SP 数据文件</b><div class="status-label">${esc(data.data_updated_at ? "服务器收到的 sp_data.db" : "未收到文件")}</div></div><span class="mono">${esc(fmtTime(data.data_updated_at, true))} · ${ageText(data.data_age_seconds)}前</span></div>
        <div class="status-item"><div><b>最近成功采集</b><div class="status-label">最近一次抓到官方 SP</div></div><span class="mono">${esc(fmtTime(data.last_success_at, true))}</span></div>
        <div class="status-item"><div><b>最近推送</b><div class="status-label">SFTP 到服务器</div></div><span class="mono">${esc(fmtTime(data.last_push_at, true))}</span></div>
      </div>
      <div class="integration-meta" style="margin-top:16px">
        <b>主机</b><span class="mono">${esc(data.host || "—")} · pid ${esc(data.pid || "—")} · ${esc(data.version || "—")}</span>
        <b>轮次</b><span>${data.cycle ?? 0} 轮 · 场次 ${data.matches ?? 0} · 快照 ${data.snapshots_total ?? 0}</span>
        <b>错误</b><span>${data.last_error ? esc(data.last_error) : "无"}</span>
        <b>重启</b><span>${data.restart_pending ? "已下发，等待采集器下一次心跳" : "无待执行指令"}</span>
      </div>
      <div class="integration-actions" style="margin-top:16px">
        ${canOperate() ? '<button class="btn secondary small" id="collector-restart">一键重启采集器</button>' : ""}
        <button class="btn ghost small" data-goto="data">查看数据源</button>
      </div>
      ${data.host ? "" : '<div class="af-warning">还没有收到心跳：请确认采集器已启动，且 JQ_COLLECTOR_TOKEN 与服务器一致。</div>'}
    </div>
  `;
  els("[data-goto]").forEach(btn => btn.onclick = () => showView(btn.dataset.goto));
  if (el("#collector-restart")) {
    el("#collector-restart").onclick = () => confirmModal(
      "重启采集器",
      "会向采集器下发重启指令。采集器在线时下一次心跳会退出，由本地 watchdog 自动拉起；离线时指令会排队。",
      async () => {
        const res = await post("/admin/api/collector/restart");
        toast(res && res.notice ? res.notice : "已下发重启指令", res && res.online ? "success" : "warn", 6000);
        loadCollector();
      },
    );
  }
}

/* ---------- integration center ---------- */


function integrationStatus(configured, enabled = true) {
  if (!enabled) return '<span class="pill muted">已停用</span>';
  return configured
    ? '<span class="pill green">已配置</span>'
    : '<span class="pill amber">未配置</span>';
}

function llmProfileCard(profile, usage, lastError) {
  const isFast = profile.name === "fast";
  const title = isFast ? "对话问答" : "发布前复核";
  const subtitle = isFast
    ? "/chat 开放问题、轻任务（fast）"
    : "决策/组合的语义复核（deep）";
  const source = profile.source === "admin" ? "后台配置"
    : profile.source === "env" ? "环境变量" : "—";
  const keyState = profile.admin_key_set ? "后台已保存 Key" : "未在后台保存 Key";
  return `
    <div class="card integration-card">
      <div class="card-head">
        <div>
          <h2 class="card-title">${title}</h2>
          <div class="card-sub">${subtitle}</div>
        </div>
        ${integrationStatus(profile.configured, profile.enabled)}
      </div>
      <div class="integration-meta">
        <b>作用</b><span>${esc(profile.purpose)}</span>
        <b>模型</b><span class="mono">${esc(profile.provider)} · ${esc(profile.model || "—")}</span>
        <b>推理</b><span>${profile.reasoning === "off" ? "关闭（enable_thinking=false）" : "自动"}</span>
        <b>接口</b><span class="mono">${esc(profile.base_url || "—")}</span>
        <b>来源</b><span>${source} · ${keyState}</span>
        <b>今日</b><span>${usage.calls} 次调用 · ¥${num(usage.cost, 4)}${lastError ? ` · 最近失败 ${esc(lastError)}` : ""}</span>
      </div>
      <div class="integration-actions">
        ${canAdmin() ? `<button class="btn secondary small" data-llm-edit="${profile.name}">配置接口</button>` : ""}
        ${canOperate() ? `<button class="btn ghost small" data-llm-test="${profile.name}" ${profile.configured ? "" : "disabled"}>测试连接</button>` : ""}
      </div>
    </div>`;
}

async function loadIntegrations() {
  const root = el("#view-integrations");
  root.innerHTML = '<div class="skeleton"></div>';
  const [llm, models, data, overview, gateway] = await Promise.all([
    api("/admin/api/llm/profiles"),
    api("/admin/api/models"),
    api("/admin/api/data"),
    api("/admin/api/overview"),
    api("/admin/api/gateway"),
  ]);
  const usageByProfile = {};
  (gateway.summary.rows || []).forEach(row => {
    const item = usageByProfile[row.profile] || { calls: 0, cost: 0 };
    item.calls += Number(row.calls || 0);
    item.cost += Number(row.cost_cny || 0);
    usageByProfile[row.profile] = item;
  });
  const lastErrorByProfile = {};
  (gateway.summary.recent || []).forEach(row => {
    if (row.status !== "ok" && row.profile && !lastErrorByProfile[row.profile]) {
      lastErrorByProfile[row.profile] = row.error_class || row.status;
    }
  });
  const personaModels = models.models || [];
  const personaEnabled = personaModels.filter(m => m.enabled);
  const personaFailing = personaEnabled.filter(m => (m.fail_count || 0) >= 3);
  const af = data.api_football || {};
  const sm = data.sportmonks || {};
  const ai = data.ai_research || {};
  const intl = (data.supply || {}).intl_odds || {};
  const sync = data.sync || {};
  const pushChannel = overview.push_channel || {};
  const pushTokens = overview.push_tokens || {};
  const deepProfile = llm.profiles.find(p => p.name === "deep");

  root.innerHTML = `
    <div class="card">
      <div class="card-head">
        <div>
          <h2 class="card-title">先选“做什么”，再配“用哪个接口”</h2>
          <div class="card-sub">LLM 接口可在本页直接上传 Base URL / Model / Key；保存 Key 后后台配置优先于环境变量。Sportmonks、推送等密钥仍在服务器环境变量，本页只做状态核对。LLM Key 加密存储，不回显。</div>
        </div>
      </div>
    </div>

    <h2 class="section-title">AI 能力</h2>
    <div class="integration-grid">
      ${llm.profiles.map(p => llmProfileCard(
        p, usageByProfile[p.name] || { calls: 0, cost: 0 }, lastErrorByProfile[p.name],
      )).join("")}
      <div class="card integration-card">
        <div class="card-head">
          <div><h2 class="card-title">人设文案</h2><div class="card-sub">三套语气改写 · 每日 19:05 预生成</div></div>
          ${integrationStatus(personaEnabled.length > 0 && personaFailing.length === 0)}
        </div>
        <div class="integration-meta">
          <b>作用</b><span>把已封存的判断改写成专家/老炮/萌系三套文案，写缓存供用户端读取。</span>
          <b>模型池</b><span>${personaEnabled.length}/${personaModels.length} 个启用${personaFailing.length ? ` · ${personaFailing.length} 个熔断` : ""}</span>
          <b>入口</b><span>文案模型池（不是 /chat 的 fast）</span>
        </div>
        <div class="integration-actions">
          <button class="btn secondary small" data-goto="models">管理文案模型池</button>
        </div>
      </div>
      <div class="card integration-card">
        <div class="card-head">
          <div><h2 class="card-title">单场 AI 解读</h2><div class="card-sub">事实包 → 情景 / 风险解释</div></div>
          ${integrationStatus(Boolean(deepProfile?.configured), deepProfile?.enabled ?? true)}
        </div>
        <div class="integration-meta">
          <b>作用</b><span>把 SP、Sportmonks 预测/市场、阵容、伤停、积分榜、概率与三闸交给 deep 模型，生成可引用的赛前解读。</span>
          <b>入口</b><span>详情页「生成 AI 解读」；只对 deep_eligible 场次生成。</span>
          <b>缓存</b><span>事实包 hash + 6 小时过期；数据变化自动重算。</span>
        </div>
        <div class="integration-actions">
          <button class="btn ghost small" data-goto="data">查看数据供给</button>
        </div>
      </div>
    </div>

    <h2 class="section-title">主数据链路</h2>
    <div class="integration-grid">
      <div class="card integration-card">
        <div class="card-head">
          <div><h2 class="card-title">Sportmonks</h2><div class="card-sub">预测 1X2 + Pinnacle 市场 · 主链路</div></div>
          ${!sm.configured ? '<span class="pill amber">未配置</span>' : Number(sm.covered) > 0 ? `<span class="pill green">覆盖 ${sm.covered}/${sm.matches}</span>` : '<span class="pill amber">待同步</span>'}
        </div>
        <div class="integration-meta">
          <b>今日覆盖</b><span>${sm.covered ?? 0}/${sm.matches ?? 0} 场${sm.missing_count ? ` · 缺失 ${sm.missing_count}` : ""}</span>
          <b>数据完整</b><span>预测 ${sm.with_probs ?? 0} · 市场 ${sm.with_odds ?? 0}</span>
          <b>最新同步</b><span>${esc(fmtTime(sm.latest, true))} · 每 30 分钟</span>
        </div>
        <div class="integration-actions"><button class="btn secondary small" data-goto="data">逐场映射与同步</button></div>
      </div>
      <div class="card integration-card">
        <div class="card-head">
          <div><h2 class="card-title">AI 情报</h2><div class="card-sub">Sportmonks 事实 → 中文摘要 · 主链路</div></div>
          ${Number(ai.ready) > 0 ? `<span class="pill green">就绪 ${ai.ready}/${ai.matches}</span>` : Number(ai.matches) > 0 ? '<span class="pill amber">待同步</span>' : '<span class="pill muted">今日无场次</span>'}
        </div>
        <div class="integration-meta">
          <b>今日就绪</b><span>${ai.ready ?? 0}/${ai.matches ?? 0} 场 · 不可用 ${ai.unavailable ?? 0}</span>
          <b>最新同步</b><span>${esc(fmtTime(ai.latest, true))} · 每 30 分钟</span>
          <b>展示</b><span>详情页「AI 情报」；只陈述事实，不输出概率</span>
        </div>
        <div class="integration-actions"><button class="btn secondary small" data-goto="data">查看逐场状态</button></div>
      </div>
      <div class="card integration-card">
        <div class="card-head">
          <div><h2 class="card-title">竞彩 SP 采集器</h2><div class="card-sub">官方在售赔率 · 主链路</div></div>
          ${sync.latest ? '<span class="pill green">有数据</span>' : '<span class="pill amber">无数据</span>'}
        </div>
        <div class="integration-meta">
          <b>最新快照</b><span>${esc(fmtTime(sync.latest, true))}</span>
          <b>同步延迟</b><span>${sync.lag_seconds == null ? "—" : `${sync.lag_seconds}s`}（超过 1800s 视为异常）</span>
          <b>位置</b><span>家宽机器 collector.py → SFTP → seed</span>
        </div>
        <div class="integration-actions"><button class="btn secondary small" data-goto="collector">查看采集器</button></div>
      </div>
    </div>

    <h2 class="section-title">辅助数据（只补缺口）</h2>
    <div class="card aux-sources">
      <div class="card-sub" style="margin-bottom:10px">主链路已收口到 Sportmonks + 竞彩 SP。下面两项只在缺口时使用，不作为发布前置。</div>
      <div class="table-wrap"><table>
        <thead><tr><th>来源</th><th>用途</th><th>状态</th><th>覆盖 / 额度</th><th></th></tr></thead>
        <tbody>
          <tr>
            <td><b>API-Football</b></td>
            <td>阵容 / 伤停 / 积分榜</td>
            <td>${af.configured ? '<span class="pill green">已配置</span>' : '<span class="pill muted">未配置</span>'}</td>
            <td>今日 ${af.used_today ?? 0}/${af.daily_limit ?? 0} 次 · 阵容 ${af.target?.lineups ?? 0} 行 · 伤停 ${af.target?.injuries ?? 0} 条</td>
            <td><button class="btn ghost small" data-goto="data">查看</button></td>
          </tr>
          <tr>
            <td><b>The Odds API</b></td>
            <td>Sportmonks 缺市场时的国际盘对照</td>
            <td>${intl.configured ? '<span class="pill green">已配置</span>' : '<span class="pill muted">未配置</span>'}</td>
            <td>覆盖 ${intl.covered_matches ?? 0} 场 · 总量 ${intl.total ?? 0} 条</td>
            <td><button class="btn ghost small" data-goto="data">查看</button></td>
          </tr>
        </tbody>
      </table></div>
    </div>

    <h2 class="section-title">推送通道</h2>
    <div class="integration-grid">
      <div class="card integration-card">
        <div class="card-head">
          <div><h2 class="card-title">JPush</h2><div class="card-sub">设备推送 / 通知</div></div>
          ${integrationStatus(Boolean(pushChannel.configured))}
        </div>
        <div class="integration-meta">
          <b>服务端</b><span>${pushChannel.configured ? "已配置" : "未配置（当前 dry-run）"}</span>
          <b>设备令牌</b><span>${pushTokens.enabled ?? 0} 启用 / ${pushTokens.total ?? 0} 总数</span>
          <b>Key 位置</b><span>服务器环境变量 JQ_JPUSH_APPKEY / JQ_JPUSH_MASTER_SECRET</span>
        </div>
      </div>
    </div>
  `;

  els("[data-goto]").forEach(btn => btn.onclick = () => showView(btn.dataset.goto));
  els("[data-llm-edit]").forEach(btn => btn.onclick = () => {
    const profile = llm.profiles.find(p => p.name === btn.dataset.llmEdit);
    if (profile) openLLMProfileModal(profile);
  });
  els("[data-llm-test]").forEach(btn => btn.onclick = async () => {
    btn.disabled = true; btn.textContent = "测试中…";
    try {
      const result = await post(`/admin/api/llm/profiles/${btn.dataset.llmTest}/test`);
      modal("连接测试", `
        <div class="detail-list"><div><b>模型</b> ${esc(result.provider)} · ${esc(result.model)}</div>
        <div><b>延迟</b> ${result.latency_ms}ms</div></div>
        <div class="card" style="margin-top:16px;white-space:pre-wrap">${esc(result.text || "（空响应）")}</div>`);
    } catch (error) { toast(error.message, "error"); }
    btn.disabled = false; btn.textContent = "测试连接";
  });
}

function openLLMProfileModal(profile) {
  const label = profile.name === "fast" ? "对话问答" : "发布前复核";
  modal(`配置 ${label}`, `
    <form id="llm-form" class="form-grid">
      <div class="full"><label>用途</label><div class="card-sub">${esc(profile.purpose)}</div></div>
      <div><label>Provider</label><input id="llm-provider" value="${esc(profile.provider || "openai_compatible")}" placeholder="deepseek / glm / tokenrhythm"></div>
      <div><label>Model ID</label><input id="llm-model" required value="${esc(profile.model || "")}" placeholder="deepseek-chat"></div>
      <div class="full"><label>Base URL</label><input id="llm-base" required value="${esc(profile.base_url || "")}" placeholder="https://api.deepseek.com/v1"></div>
      <div class="full"><label>API Key ${profile.admin_key_set ? "（已保存，留空不修改）" : ""}</label><input id="llm-key" type="password" placeholder="sk-..."><div class="card-sub" style="margin-top:6px">未保存过 Key 时，留空会整组沿用环境变量；修改 Base URL/Model 请同时填 Key。</div></div>
      <div><label>输入价 ¥/百万 tokens</label><input id="llm-in" type="number" min="0" step="0.01" value="${profile.input_price_cny_per_m ?? 0}"></div>
      <div><label>输出价 ¥/百万 tokens</label><input id="llm-out" type="number" min="0" step="0.01" value="${profile.output_price_cny_per_m ?? 0}"></div>
      <div><label>启用</label><select id="llm-enabled"><option value="true" ${profile.enabled ? "selected" : ""}>启用</option><option value="false" ${!profile.enabled ? "selected" : ""}>停用</option></select></div>
      <div><label>推理</label><select id="llm-reasoning">
        <option value="auto" ${(profile.reasoning || "auto") === "auto" ? "selected" : ""}>自动（模型默认）</option>
        <option value="off" ${profile.reasoning === "off" ? "selected" : ""}>关闭（enable_thinking=false）</option>
      </select></div>
      ${profile.admin_key_set ? '<div><label>清除已保存 Key</label><select id="llm-clear"><option value="false">否</option><option value="true">是</option></select></div>' : ""}
      <div class="actions full">
        <button class="btn primary" type="submit">保存</button>
        <button class="btn secondary" type="button" id="llm-save-test">保存并测试</button>
        <button class="btn ghost" type="button" id="llm-cancel">取消</button>
      </div>
    </form>`);
  const save = async () => {
    const key = el("#llm-key").value.trim();
    const body = {
      provider: el("#llm-provider").value.trim() || "openai_compatible",
      base_url: el("#llm-base").value.trim(),
      model: el("#llm-model").value.trim(),
      api_key: key || null,
      clear_key: el("#llm-clear") ? el("#llm-clear").value === "true" : false,
      input_price_cny_per_m: Number(el("#llm-in").value || 0),
      output_price_cny_per_m: Number(el("#llm-out").value || 0),
      enabled: el("#llm-enabled").value === "true",
      reasoning: el("#llm-reasoning").value,
    };
    await put(`/admin/api/llm/profiles/${profile.name}`, body);
  };
  el("#llm-form").onsubmit = async event => {
    event.preventDefault();
    try { await save(); toast("已保存"); closeModal(); loadIntegrations(); }
    catch (error) { toast(error.message, "error"); }
  };
  el("#llm-save-test").onclick = async () => {
    try {
      await save();
      const result = await post(`/admin/api/llm/profiles/${profile.name}/test`);
      modal("连接测试", `
        <div class="detail-list"><div><b>模型</b> ${esc(result.provider)} · ${esc(result.model)}</div>
        <div><b>延迟</b> ${result.latency_ms}ms</div></div>
        <div class="card" style="margin-top:16px;white-space:pre-wrap">${esc(result.text || "（空响应）")}</div>`);
      loadIntegrations();
    } catch (error) { toast(error.message, "error"); }
  };
  el("#llm-cancel").onclick = closeModal;
}

/* ---------- gateway / plans / data / logs ---------- */

const TASK_META = {
  open_chat: { label: "对话问答", connected: true },
  decision_review: { label: "单场发布复核", connected: true },
  plan_review: { label: "组合发布复核", connected: true },
  match_analysis: { label: "单场实时分析", connected: true },
};
const PROFILE_LABEL = { fast: "对话问答（fast）", deep: "发布前复核（deep）" };

async function loadGateway() {
  const root = el("#view-gateway");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api("/admin/api/gateway");
  const rows = data.summary.rows || [];
  root.innerHTML = `
    <div class="kpi-grid auto">
      ${data.profiles.map(profile => `
        <div class="kpi ${profile.configured ? "green" : "amber"}"><div class="kpi-label">${esc(PROFILE_LABEL[profile.name] || profile.name)}</div><div class="kpi-value">${profile.configured ? "已配" : "未配"}</div><div class="kpi-foot">${esc(profile.source === "admin" ? "后台" : profile.source === "env" ? "环境变量" : "未配置")} · ${esc(profile.provider)} · ${esc(profile.model)}</div></div>`).join("")}
    </div>
    <div class="card"><h2 class="card-title">任务路由</h2><div class="table-wrap"><table><thead><tr><th>用途</th><th>配置</th><th>状态</th></tr></thead><tbody>
      ${Object.entries(data.routes || {}).map(([task, profile]) => {
        const meta = TASK_META[task] || { label: task, connected: true };
        return `<tr><td>${esc(meta.label)}</td><td>${esc(PROFILE_LABEL[profile] || profile)}</td><td>${meta.connected ? statusPill("ok") : '<span class="pill muted">未接入</span>'}</td></tr>`;
      }).join("")}
    </tbody></table></div></div>
    <div class="card"><h2 class="card-title">今日用量</h2><div class="table-wrap"><table><thead><tr><th>任务</th><th>配置</th><th class="num">调用</th><th class="num">缓存</th><th class="num">Tokens</th><th class="num">成本</th></tr></thead><tbody>
      ${rows.map(row => `<tr><td>${esc(row.task)}</td><td>${esc(row.profile)}</td><td class="num">${row.calls}</td><td class="num">${row.cache_hits}</td><td class="num">${row.input_tokens}/${row.output_tokens}</td><td class="num">¥${num(row.cost_cny, 5)}</td></tr>`).join("") || '<tr><td colspan="6">今日无调用</td></tr>'}
    </tbody></table></div></div>
    <div class="card"><h2 class="card-title">最近调用</h2><div class="table-wrap"><table><thead><tr><th>任务</th><th>模型</th><th>状态</th><th class="num">延迟</th><th class="num">成本</th></tr></thead><tbody>
      ${(data.summary.recent || []).map(u => `<tr><td>${esc(TASK_META[u.task]?.label || u.task)}</td><td>${esc(u.model)}</td><td>${statusPill(u.status)}</td><td class="num">${u.latency_ms}ms</td><td class="num">¥${num(u.cost_cny, 6)}</td></tr>`).join("") || '<tr><td colspan="5">暂无调用</td></tr>'}
    </tbody></table></div></div>
  `;
}

async function loadPlans() {
  const root = el("#view-plans");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api(`/admin/api/plans-preview?date=${encodeURIComponent(state.date)}&stake=100`);
  root.innerHTML = `
    <div class="card"><div class="toolbar"><div><h2 style="margin:0">确定性组合预览</h2><div class="card-sub" style="margin:0">候选 ${data.candidates} · 仅预览，正式发布需走推荐主链</div></div><button class="btn secondary" id="reload-plans">刷新</button></div>
      ${data.plans.map(plan => `
        <div class="reco-card draft">
          <div class="reco-head"><div><div class="reco-title">${esc(plan.label)} · ${plan.legs.length} 串 1</div><div class="reco-sub">组合赔率 ${plan.check.combo.odds} · 成本 ${plan.check.combo.cost}</div></div>${statusPill("draft")}</div>
          <div class="detail-list" style="margin-top:12px">${plan.check.legs.map(leg => `<div><b>${esc(leg.match_no)}</b> ${esc(leg.home)} vs ${esc(leg.away)} · ${esc(leg.dir_label)} @${leg.odds} · ${esc(leg.status)}</div>`).join("")}</div>
          ${plan.note ? `<div class="model-error warn">${esc(plan.note)}</div>` : ""}
        </div>`).join("") || '<div class="empty">' + (data.candidates ? `候选 ${data.candidates} 场，暂无满足相关性与成本条件的组合。` : '今日暂无候选场次。') + '</div>'}
    </div>
  `;
  el("#reload-plans").onclick = loadPlans;
}

async function loadData() {
  const root = el("#view-data");
  root.innerHTML = '<div class="skeleton"></div>';
  const [data, matrix] = await Promise.all([
    api("/admin/api/data"),
    api("/admin/api/sportmonks/matrix"),
  ]);
  const supply = data.supply || {};
  const gate = supply.market_gate || {};
  const intl = supply.intl_odds || {};
  const af = data.api_football || {};
  const published = supply.published ?? 0;
  const summary = matrix.summary || {};
  const pct = value => value == null ? "—" : `${Math.round(Number(value) * 100)}%`;
  const triple = probs => {
    if (!probs) return '<span class="card-sub">—</span>';
    return `<div class="triple"><span>主 ${pct(probs.home)}</span><span>平 ${pct(probs.draw)}</span><span>客 ${pct(probs.away)}</span></div>`;
  };
  const rows = (matrix.rows || []).map(row => {
    const sm = row.mapped
      ? `<span class="pill ${row.source === "manual" ? "blue" : "green"}">${row.source === "manual" ? "手动" : "自动"}</span><div class="card-sub mono">#${row.fixture_id}</div>`
      : '<span class="pill amber">未映射</span>';
    const intel = row.intel.status === "ready"
      ? `<span class="pill green">就绪</span><div class="card-sub ellipsis" title="${esc(row.intel.headline)}">${esc(row.intel.headline || "")}</div>`
      : row.intel.status
        ? statusPill(row.intel.status)
        : '<span class="pill muted">未同步</span>';
    const v = row.verdict;
    const verdict = v
      ? `${statusPill(v.status)}${v.pick && v.pick.dir ? `<div class="card-sub">${esc(v.pick.dir)}</div>` : ""}${v.result_score ? `<div class="card-sub mono">${esc(v.result_score)} · ${esc(v.settled || "待结算")}</div>` : ""}`
      : '<span class="pill muted">无判决</span>';
    return `<tr>
      <td><b>${esc(row.match_no)}</b>${row.single_flag ? '<div class="card-sub">单关</div>' : ""}</td>
      <td class="teams"><b>${esc(row.home)}</b><span>vs ${esc(row.away)}</span><div class="card-sub">${esc(row.league)}</div></td>
      <td class="mono">${esc((row.kickoff || "").slice(5, 16))}</td>
      <td>${sm}</td>
      <td>${triple(row.probs)}</td>
      <td>${triple(row.odds)}${row.bookmaker ? `<div class="card-sub">${esc(row.bookmaker)}</div>` : ""}${row.mapped && row.odds && !row.odds_fresh ? '<div><span class="pill amber">已过期</span></div>' : ""}</td>
      <td>${intel}</td>
      <td>${verdict}</td>
      <td class="row-actions">
        <button class="btn ghost small" data-sm-map="${esc(row.match_id)}">${row.mapped ? "改映射" : "手动映射"}</button>
        ${row.mapped ? `<button class="btn secondary small" data-sm-resync="${esc(row.match_id)}" data-fixture="${row.fixture_id}">重拉</button>` : ""}
        ${row.mapped ? `<button class="btn ghost small danger" data-sm-unmap="${esc(row.match_id)}">解除</button>` : ""}
      </td>
    </tr>`;
  }).join("");

  root.innerHTML = `
    ${supply.blocked_reason ? `<div class="card notice"><b>内容供给受阻：${esc(supply.blocked_reason)}</b><div class="card-sub" style="margin-top:8px">场次 ${supply.matches ?? 0} · 判决 ${supply.verdicts?.total ?? 0} · 市闸 pending ${gate.pending_data ?? 0} · 未开赛覆盖 ${supply.market_covered_matches ?? 0}/${supply.upcoming_matches ?? supply.matches ?? 0} 场（SM ${supply.sportmonks_market?.covered_matches ?? 0} · 辅助国际盘 ${intl.covered_matches ?? 0}）</div></div>` : ""}
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">今日场次</div><div class="kpi-value">${summary.matches ?? 0}</div><div class="kpi-foot">已发布 ${published}</div></div>
      <div class="kpi green accent"><div class="kpi-label">SM 映射</div><div class="kpi-value">${summary.mapped ?? 0}/${summary.matches ?? 0}</div><div class="kpi-foot">手动 ${summary.manual ?? 0} · 缺失 ${summary.missing ?? 0}</div></div>
      <div class="kpi"><div class="kpi-label">SM 预测</div><div class="kpi-value">${summary.with_probs ?? 0}</div><div class="kpi-foot">市场赔率 ${summary.with_odds ?? 0}</div></div>
      <div class="kpi"><div class="kpi-label">AI 情报</div><div class="kpi-value">${summary.intel_ready ?? 0}</div><div class="kpi-foot">就绪 / ${summary.matches ?? 0} 场</div></div>
    </div>
    <div class="card"><h2 class="card-title">内容供给</h2>
      <div class="flow">
        <div class="flow-step">
          <div class="flow-index">01</div><div class="flow-label">今日场次</div>
          <div class="flow-value">${supply.matches ?? 0}</div>
          <div class="flow-meta">SP 快照 ${supply.sp_snapshots ?? 0} 行</div>
        </div>
        <div class="flow-step">
          <div class="flow-index">02</div><div class="flow-label">Sportmonks</div>
          <div class="flow-value">${summary.mapped ?? 0}</div>
          <div class="flow-meta">预测 ${summary.with_probs ?? 0} · 市场 ${summary.with_odds ?? 0}</div>
        </div>
        <div class="flow-step">
          <div class="flow-index">03</div><div class="flow-label">市闸</div>
          <div class="flow-value">${gate.pass ?? 0} 过</div>
          <div class="flow-meta">${gate.pending_data ?? 0} 待 · ${gate.fail ?? 0} 败</div>
        </div>
        <div class="flow-step">
          <div class="flow-index">04</div><div class="flow-label">已发布</div>
          <div class="flow-value">${published}</div>
          <div class="flow-meta">snapshot ${supply.snapshots?.published ?? 0} · plan ${supply.plans?.published ?? 0}</div>
        </div>
      </div>
    </div>
    <div class="card sm-matrix">
      <div class="toolbar">
        <div><h2 style="margin:0">今日数据矩阵</h2><div class="card-sub" style="margin:0">${esc(matrix.date)} · 竞彩场次 × Sportmonks × AI 情报 × 判决；30 分钟自动同步</div></div>
        <div class="actions">
          <button class="btn secondary small" id="sm-sync">同步 Sportmonks</button>
          <button class="btn secondary small" id="intel-sync">同步 AI 情报</button>
          <button class="btn ghost small" id="results-sync">回填赛果</button>
        </div>
      </div>
      ${rows ? `<div class="table-wrap"><table><thead><tr>
        <th>场次</th><th>对阵</th><th>开赛</th><th>SM 映射</th>
        <th>SM 预测</th><th>SM 市场</th><th>AI 情报</th><th>判决</th><th>操作</th>
      </tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty">今日暂无竞彩场次</div>'}
      <div class="card-sub" style="margin-top:10px">SP 最新快照 ${esc(fmtTime(data.sync?.latest, true))} · 延迟 ${data.sync?.lag_seconds == null ? "—" : `${data.sync.lag_seconds}s`} · 手动映射会立即拉取预测、Pinnacle 1X2 与中文情报。</div>
    </div>
    <div class="card">
      <div class="toolbar"><div><h2 style="margin:0">辅助数据</h2><div class="card-sub" style="margin:0">只补阵容/伤停和国际盘缺口；不作为发布前置</div></div>
        <button class="btn ghost small" data-goto="integrations">接入中心</button></div>
      <div class="status-grid">
        <div class="status-item"><div><b>API-Football</b><div class="status-label">阵容 / 伤停 / 积分榜</div></div><span class="mono">今日 ${af.used_today ?? 0}/${af.daily_limit ?? 0} 次 · 阵容 ${af.target?.lineups ?? 0} 行 · 伤停 ${af.target?.injuries ?? 0} 条</span></div>
        <div class="status-item"><div><b>The Odds API</b><div class="status-label">Sportmonks 缺市场时的国际盘对照</div></div><span class="mono">${intl.covered_matches ?? 0}/${supply.matches ?? 0} 场</span></div>
      </div>
      ${(af.warnings || []).length ? `<div class="card-sub" style="margin-top:10px">${af.warnings.map(w => esc(w)).join("；")}</div>` : ""}
    </div>
  `;

  const smSync = el("#sm-sync");
  if (smSync) smSync.onclick = async () => {
    smSync.disabled = true; smSync.textContent = "同步中…";
    try {
      const r = await post("/admin/api/sportmonks/sync", {});
      if (r.ok === false) throw new Error(r.reason || "同步失败");
      toast(`Sportmonks 同步：${r.synced}/${r.total_matches ?? r.matches}${r.truncated ? ` · 截断 ${r.truncated}` : ""}`);
      await loadData();
    }
    catch (e) { toast(e.message, "error"); smSync.disabled = false; smSync.textContent = "同步 Sportmonks"; }
  };
  const intelSync = el("#intel-sync");
  if (intelSync) intelSync.onclick = async () => {
    intelSync.disabled = true; intelSync.textContent = "同步中…";
    try {
      const r = await post("/admin/api/ai-research/sync", {});
      if (r.ok === false) throw new Error(r.reason || "同步失败");
      toast(`AI 情报：${r.synced}/${r.matches}`);
      await loadData();
    }
    catch (e) { toast(e.message, "error"); intelSync.disabled = false; intelSync.textContent = "同步 AI 情报"; }
  };
  const resultsSync = el("#results-sync");
  if (resultsSync) resultsSync.onclick = async () => {
    resultsSync.disabled = true; resultsSync.textContent = "回填中…";
    try {
      const r = await post("/admin/api/sportmonks/results", { days: 2 });
      if (r.ok === false) throw new Error(r.reason || "赛果回填失败");
      const b = await post("/admin/api/sportmonks/results/backfill", { days: 14 });
      if (b.ok === false) throw new Error(b.reason || "历史赛果回填失败");
      toast(`赛果：新增 ${r.inserted} 场 · 历史 ${b.inserted} 场 · 结算 ${Number(r.settled || 0) + Number(b.settled || 0)} 注`);
      await loadData();
    } catch (e) { toast(e.message, "error"); resultsSync.disabled = false; resultsSync.textContent = "回填赛果"; }
  };
  els("[data-sm-map]").forEach(btn => btn.onclick = () => openSportmonksMapping(btn.dataset.smMap));
  els("[data-sm-resync]").forEach(btn => btn.onclick = async () => {
    const matchId = btn.dataset.smResync;
    const fixtureId = Number(btn.dataset.fixture);
    if (!matchId || !fixtureId) return;
    btn.disabled = true; btn.textContent = "同步中…";
    try {
      const r = await post("/admin/api/sportmonks/map", { match_id: matchId, fixture_id: fixtureId });
      toast(`已重拉 ${r.home || ""} vs ${r.away || ""}${r.intel ? " · 情报已刷新" : ""}`);
      await loadData();
    } catch (e) { toast(e.message, "error"); btn.disabled = false; btn.textContent = "重拉"; }
  });
  els("[data-sm-unmap]").forEach(btn => btn.onclick = async () => {
    const matchId = btn.dataset.smUnmap;
    if (!confirm("解除映射会同时删除该场 AI 情报，确认？")) return;
    try { await del(`/admin/api/sportmonks/map/${encodeURIComponent(matchId)}`); toast("已解除映射"); await loadData(); }
    catch (e) { toast(e.message, "error"); }
  });
  els("[data-goto]").forEach(btn => btn.onclick = () => showView(btn.dataset.goto));
}

async function openSportmonksMapping(matchId) {
  modal("映射 Sportmonks fixture", '<div class="skeleton"></div>');
  try {
    const data = await api(`/admin/api/sportmonks/candidates?match_id=${encodeURIComponent(matchId)}`);
    const match = data.match || {};
    const candidates = data.candidates || [];
    const bind = async fixtureId => {
      try {
        const r = await post("/admin/api/sportmonks/map", { match_id: matchId, fixture_id: fixtureId });
        toast(`已绑定 fixture ${r.fixture_id}${r.intel ? " · 情报已刷新" : ""}`);
        closeModal();
        await loadData();
      } catch (error) { toast(error.message, "error"); }
    };
    el("#modal-card").innerHTML = `<h3>映射 Sportmonks fixture</h3>
      <div class="card-sub" style="margin-bottom:12px">竞彩 ${esc(match.match_no || "")} · ${esc(match.home || "")} vs ${esc(match.away || "")} · ${esc(match.kickoff || "")}<br>候选范围：开球前后 6 小时；只绑定确认是同一场的 fixture。</div>
      ${candidates.length ? `<div class="table-wrap"><table><thead><tr>
        <th>Fixture</th><th>联赛</th><th>Sportmonks 对阵</th><th>开球差</th><th>相似度</th><th>状态</th><th></th>
      </tr></thead><tbody>${candidates.map(c => `<tr>
        <td class="mono">#${c.fixture_id}</td>
        <td>${esc(c.league)}</td>
        <td>${esc(c.home)} vs ${esc(c.away)}</td>
        <td class="mono">${c.delta_min > 0 ? "+" : ""}${c.delta_min} 分</td>
        <td class="mono">${c.home_sim} / ${c.away_sim}</td>
        <td>${c.mapped_to && c.mapped_to !== matchId ? `<span class="pill amber">已绑 ${esc(c.mapped_to)}</span>` : c.suggested ? '<span class="pill green">自动匹配</span>' : '<span class="pill muted">候选</span>'}</td>
        <td><button class="btn primary small" data-pick="${c.fixture_id}" ${c.mapped_to && c.mapped_to !== matchId ? "disabled" : ""}>绑定</button></td>
      </tr>`).join("")}</tbody></table></div>` : '<div class="empty">前后 6 小时没有 Sportmonks fixture；检查联赛是否在 Sportmonks 覆盖范围。</div>'}
      <div class="actions" style="margin-top:12px"><button class="btn ghost" id="map-cancel">取消</button></div>`;
    els("[data-pick]").forEach(btn => btn.onclick = () => bind(Number(btn.dataset.pick)));
    const cancel = el("#map-cancel");
    if (cancel) cancel.onclick = closeModal;
  } catch (error) {
    el("#modal-card").innerHTML = `<h3>映射 Sportmonks fixture</h3><div class="empty">${esc(error.message)}</div>`;
  }
}

async function loadModelEval() {
  const root = el("#view-model-eval");
  root.innerHTML = '<div class="skeleton"></div>';
  const days = state.modelEvalDays || 90;
  const data = await api(`/admin/api/model-eval?days=${days}`);
  const overall = data.overall || {};
  const pct = value => value == null ? "—" : `${Math.round(Number(value) * 100)}%`;
  const brier = value => value == null ? "—" : Number(value).toFixed(3);
  const top = probs => {
    if (!probs) return "—";
    const key = ["home", "draw", "away"].reduce(
      (best, k) => Number(probs[k] || 0) > Number(probs[best] || 0) ? k : best, "home");
    return `${({ home: "主", draw: "平", away: "客" })[key]} ${pct(probs[key])}`;
  };
  const baseline = overall.market_model_brier ?? overall.market_brier;
  const delta = overall.model_brier != null && baseline != null
    ? Number(baseline) - Number(overall.model_brier) : null;
  const leagueRows = (data.leagues || []).map(row => {
    const rowBaseline = row.market_model_brier ?? row.market_brier;
    const diff = row.model_brier != null && rowBaseline != null
      ? Number(rowBaseline) - Number(row.model_brier) : null;
    const signal = row.model_samples < 10
      ? '<span class="pill muted">样本不足</span>'
      : diff != null && diff > 0
        ? '<span class="pill green">模型更优</span>'
        : '<span class="pill amber">基线更优</span>';
    return `<tr>
      <td><b>${esc(row.league)}</b></td>
      <td class="num">${row.samples}</td>
      <td class="num">${row.model_samples}</td>
      <td class="num">${brier(row.model_brier)}</td>
      <td class="num">${brier(rowBaseline)}<div class="card-sub">全样本 ${brier(row.market_brier)}</div></td>
      <td class="num">${brier(row.sm_odds_brier)}<div class="card-sub">${row.sm_odds_samples} 场</div></td>
      <td class="num">${brier(row.sm_model_brier)}<div class="card-sub">${row.sm_model_samples} 场</div></td>
      <td class="num">${row.model_top_rate == null ? "—" : pct(row.model_top_rate)}</td>
      <td>${signal}</td>
    </tr>`;
  }).join("");
  const recentRows = (data.recent || []).map(row => `<tr>
    <td class="mono">${esc(row.trade_date)}</td>
    <td>${esc(row.league)}<div class="card-sub">${esc(row.home)} vs ${esc(row.away)}</div></td>
    <td class="mono">${esc(row.score || "—")}</td>
    <td>${({ home: "主胜", draw: "平", away: "客胜" })[row.outcome] || esc(row.outcome)}</td>
    <td>${top(row.model)}</td>
    <td>${top(row.market)}</td>
    <td>${top(row.sm_odds)}</td>
    <td>${top(row.sm_model)}</td>
    <td>${statusPill(row.status)}</td>
  </tr>`).join("");
  root.innerHTML = `
    <div class="card">
      <div class="toolbar">
        <div><h2 style="margin:0">概率质量对比</h2><div class="card-sub" style="margin:0">已结算场次 · Brier 越低越好 · 样本窗口内只统计有赛果的比赛</div></div>
        <select id="eval-days" style="max-width:160px">
          ${[30, 90, 180, 365].map(d => `<option value="${d}" ${days === d ? "selected" : ""}>近 ${d} 天</option>`).join("")}
        </select>
      </div>
      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-label">结算样本</div><div class="kpi-value">${overall.samples ?? 0}</div><div class="kpi-foot">模型样本 ${overall.model_samples ?? 0}</div></div>
        <div class="kpi ${delta != null && delta > 0 ? "green accent" : ""}"><div class="kpi-label">模型 Brier</div><div class="kpi-value">${brier(overall.model_brier)}</div><div class="kpi-foot">Top1 命中 ${overall.model_top_rate == null ? "—" : pct(overall.model_top_rate)}</div></div>
        <div class="kpi"><div class="kpi-label">竞彩基线（同模型样本）</div><div class="kpi-value">${brier(baseline)}</div><div class="kpi-foot">全样本 ${brier(overall.market_brier)}</div></div>
        <div class="kpi"><div class="kpi-label">SM 市场</div><div class="kpi-value">${brier(overall.sm_odds_brier)}</div><div class="kpi-foot">Pinnacle 1X2 · ${overall.sm_odds_samples ?? 0} 场</div></div>
        <div class="kpi"><div class="kpi-label">SM 预测</div><div class="kpi-value">${brier(overall.sm_model_brier)}</div><div class="kpi-foot">模型 237 · ${overall.sm_model_samples ?? 0} 场</div></div>
      </div>
      <div class="card-sub">${delta == null ? "模型样本不足，暂不能判断模型是否优于竞彩基线。" : delta > 0 ? `模型 Brier 比同批样本的竞彩基线低 ${delta.toFixed(3)}，当前样本下模型有增量。` : `模型 Brier 比同批样本的竞彩基线高 ${Math.abs(delta).toFixed(3)}，当前样本下不具备优势。`} 分联赛样本 ≥10 才显示结论；上线前仍需按联赛做样本外验证。</div>
    </div>
    <div class="card"><h2 class="card-title">分联赛</h2>
      ${leagueRows ? `<div class="table-wrap"><table><thead><tr>
        <th>联赛</th><th class="num">结算</th><th class="num">模型样本</th>
        <th class="num">模型</th><th class="num">竞彩基线</th>
        <th class="num">SM 市场</th><th class="num">SM 预测</th>
        <th class="num">Top1</th><th>结论</th>
      </tr></thead><tbody>${leagueRows}</tbody></table></div>` : '<div class="empty">窗口内还没有已结算且带赛果的场次。</div>'}
    </div>
    <div class="card"><h2 class="card-title">最近结算</h2>
      ${recentRows ? `<div class="table-wrap"><table><thead><tr>
        <th>日期</th><th>场次</th><th>比分</th><th>赛果</th>
        <th>模型 Top1</th><th>竞彩 Top1</th><th>SM 市场 Top1</th><th>SM 预测 Top1</th><th>判决</th>
      </tr></thead><tbody>${recentRows}</tbody></table></div>` : '<div class="empty">暂无结算记录。</div>'}
    </div>
  `;
  const select = el("#eval-days");
  if (select) select.onchange = () => { state.modelEvalDays = Number(select.value); loadModelEval(); };
}

async function loadLogs() {
  const root = el("#view-logs");
  root.innerHTML = `
    <div class="card">
      <div class="toolbar"><div><h2 style="margin:0">运行日志</h2><div class="card-sub" style="margin:0">只读最近日志，不做文件遍历</div></div>
      <select id="log-name">${["sync", "sportmonks", "intel", "recommendations", "persona", "assistant", "purge", "db_maint", "backtest"].map(x => `<option value="${x}" ${state.logName === x ? "selected" : ""}>${x}.log</option>`).join("")}</select></div>
      <div id="log-box" class="terminal">加载中…</div>
    </div>
  `;
  const load = async () => {
    const data = await api(`/admin/api/logs?name=${encodeURIComponent(state.logName)}&lines=300`);
    el("#log-box").textContent = (data.lines || []).join("") || "日志为空";
    el("#log-box").scrollTop = el("#log-box").scrollHeight;
  };
  el("#log-name").onchange = event => { state.logName = event.target.value; load(); };
  await load();
}

/* ---------- shell ---------- */

const views = {
  overview: { title: "总览", kicker: "今日运营", loader: loadOverview },
  workbench: { title: "工作台", kicker: "全链路健康", loader: loadWorkbench },
  collector: { title: "采集器", kicker: "家宽心跳", loader: loadCollector },
  integrations: { title: "接入中心", kicker: "AI 能力与接口", loader: loadIntegrations },
  models: { title: "文案模型池", kicker: "人设文案模型", loader: loadModels },
  gateway: { title: "调用用量", kicker: "调用与成本", loader: loadGateway },
  personas: { title: "人设文案", kicker: "文案语气", loader: loadPersonas },
  recommendations: { title: "推荐主链", kicker: "判断发布", loader: loadRecommendations },
  plans: { title: "组合预览", kicker: "风险组合", loader: loadPlans },
  data: { title: "数据源", kicker: "数据供给", loader: loadData },
  "model-eval": { title: "模型效果", kicker: "概率质量", loader: loadModelEval },
  logs: { title: "运行日志", kicker: "运行输出", loader: loadLogs },
};

let autoTimer = null;
const AUTO_VIEWS = new Set(["workbench", "overview", "recommendations", "gateway", "data", "model-eval", "models", "integrations", "collector"]);

function scheduleAutoRefresh() {
  clearInterval(autoTimer);
  if (!state.autoRefresh) return;
  autoTimer = setInterval(() => {
    if (document.visibilityState !== "visible") return;
    if (!el("#modal").hidden) return;
    if (document.activeElement && ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if (!AUTO_VIEWS.has(state.view)) return;
    showView(state.view);
  }, 60_000);
}

async function showView(view) {
  state.view = view;
  els(".nav-item").forEach(item => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  els(".view").forEach(section => section.classList.toggle("active", section.id === `view-${view}`));
  el("#page-title").textContent = views[view].title;
  el("#page-kicker").textContent = views[view].kicker;
  try {
    await views[view].loader();
    el("#last-updated").textContent = `更新 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
  } catch (error) {
    if (error.message !== "需要控制台登录") {
      el(`#view-${view}`).innerHTML = `<div class="empty"><b>加载失败：</b>${esc(error.message)}</div>`;
      toast(error.message, "error");
    }
  }
  scheduleAutoRefresh();
}

async function bootstrap() {
  try {
    const session = await api("/admin/api/session");
    if (!session.authenticated) return showLogin();
    ensureCsrf(session);
    state.date = session.date || "";
    el("#current-date").textContent = state.date;
    state.role = session.role || "";
    el("#env-pill").textContent = `${session.env} · ${session.role} · ${session.username}`;
    applyRole();
    showApp();
    await showView("workbench");
  } catch (_) { showLogin(); }
}

el("#login-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.target.querySelector("button");
  button.disabled = true; button.textContent = "验证中…";
  try {
    const session = await api("/admin/api/login", {
      method: "POST",
      body: {
        username: el("#username").value,
        password: el("#password").value,
      },
    });
    ensureCsrf(session);
    state.date = session.date || "";
    el("#current-date").textContent = state.date;
    state.role = session.role || "";
    el("#env-pill").textContent = `${session.env} · ${session.role} · ${session.username}`;
    applyRole();
    showApp();
    await showView("workbench");
    toast("已进入控制台");
  } catch (error) {
    el("#login-error").textContent = error.message;
  }
  button.disabled = false; button.textContent = "进入控制台";
});

el("#refresh").onclick = () => showView(state.view);
el("#auto-refresh").onclick = () => {
  state.autoRefresh = !state.autoRefresh;
  el("#auto-refresh").textContent = `自动刷新 · ${state.autoRefresh ? "开" : "关"}`;
  scheduleAutoRefresh();
};
el("#logout").onclick = async () => {
  clearInterval(autoTimer);
  await api("/admin/api/logout", { method: "POST", body: {} });
  showLogin();
};
els(".nav-item").forEach(item => item.onclick = () => showView(item.dataset.view));
el("#modal").addEventListener("click", event => { if (event.target === el("#modal")) closeModal(); });
document.addEventListener("keydown", event => { if (event.key === "Escape" && !el("#modal").hidden) closeModal(); });

bootstrap();
