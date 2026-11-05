/* 运维 / 账号 / 审计：与 admin.js 共享全局作用域，按需扩展 views。 */

async function loadOps() {
  const root = el("#view-ops");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api("/admin/api/ops");
  const alerts = data.alerts || [];
  root.innerHTML = `
    <div class="card">
      <h2 class="card-title">告警</h2>
      ${alerts.length ? alerts.map(a => `
        <div class="status-item">
          <div><div style="display:flex;gap:8px;align-items:center"><b>${esc(a.title)}</b>${statusPill(a.level === "high" ? "fail" : "skip")}</div><div class="status-label">${esc(a.detail)}</div></div>
        </div>`).join("") : '<div class="empty">无告警</div>'}
    </div>
    ${(data.supply?.blocked_reason) ? `<div class="card notice"><b>内容供给受阻：${esc(data.supply.blocked_reason)}</b><div class="card-sub" style="margin-top:8px">场次 ${data.supply.matches ?? 0} · 判决 ${data.supply.verdicts?.total ?? 0} · 市闸 pending ${data.supply.market_gate?.pending_data ?? 0} · 国际盘 ${data.supply.intl_odds?.total ?? 0}</div></div>` : ""}
    <div class="kpi-grid">
      <div class="kpi accent ${data.sync?.lag_seconds == null ? "" : data.sync.lag_seconds > 1800 ? "red" : "green"}"><div class="kpi-label">SP 延迟</div><div class="kpi-value">${data.sync?.lag_seconds == null ? "—" : data.sync.lag_seconds + "s"}</div><div class="kpi-foot">${esc(data.sync?.latest || "—")}</div></div>
      <div class="kpi"><div class="kpi-label">封存链</div><div class="kpi-value">${data.chain?.ok ? "OK" : "BAD"}</div><div class="kpi-foot">${esc(data.chain?.date || "—")} · ${esc(data.chain?.broken_at || "")}</div></div>
      <div class="kpi"><div class="kpi-label">通知队列</div><div class="kpi-value">${Object.values(data.notifications || {}).reduce((a, b) => a + Number(b || 0), 0)}</div><div class="kpi-foot">${Object.entries(data.notifications || {}).map(([k, v]) => `${esc(k)} ${v}`).join(" · ") || "—"}</div></div>
      <div class="kpi"><div class="kpi-label">Push Token</div><div class="kpi-value">${data.push_tokens?.enabled || 0}/${data.push_tokens?.total || 0}</div><div class="kpi-foot">启用 / 总数</div></div>
    </div>
    <div class="grid side">
      <div class="card"><h2 class="card-title">内容供给</h2>
        <div class="status-grid">
          <div class="status-item"><span class="status-label">今日场次 / SP</span><b>${data.supply?.matches ?? 0} / ${data.supply?.sp_snapshots ?? 0}</b></div>
          <div class="status-item"><span class="status-label">国际盘行数</span><b>${data.supply?.intl_odds?.total ?? 0}</b></div>
          <div class="status-item"><span class="status-label">国际盘覆盖</span><b>${data.supply?.intl_odds?.covered_matches ?? 0}/${data.supply?.matches ?? 0} 场</b></div>
          <div class="status-item"><span class="status-label">市闸 pass / pending</span><b>${data.supply?.market_gate?.pass ?? 0} / ${data.supply?.market_gate?.pending_data ?? 0}</b></div>
          <div class="status-item"><span class="status-label">promoted / published</span><b>${data.supply?.verdicts?.promoted ?? 0} / ${data.supply?.published ?? 0}</b></div>
          <div class="status-item"><span class="status-label">最近国际盘同步</span><b class="mono">${esc(data.supply?.intl_odds?.latest || "—")}</b></div>
        </div>
      </div>
      <div class="card"><h2 class="card-title">API-Football</h2><div class="status-grid tight">${Object.entries(data.football || {}).map(([key, value]) => `
        <div class="status-item"><div class="status-label">${esc(key)}</div><b class="mono">${esc(typeof value === "object" ? JSON.stringify(value) : String(value))}</b></div>`).join("")}</div></div>
      <div class="card span-2"><h2 class="card-title">24h 互动</h2>${Object.entries(data.interactions_24h || {}).map(([key, value]) => `
        <div class="status-item"><span class="status-label">${esc(key)}</span><b>${value}</b></div>`).join("") || '<div class="empty">暂无互动</div>'}</div>
    </div>
    <div class="card"><h2 class="card-title">API-Football 赛程</h2>
      <div class="table-wrap"><table><thead><tr><th>Fixture</th><th>时间</th><th>对阵</th><th>联赛</th><th>状态</th><th>链接</th></tr></thead><tbody>
        ${(data.football_fixtures || []).map(f => `<tr>
          <td class="mono">${f.fixture_id}</td><td class="mono">${esc(fmtTime(f.kickoff_utc, true))} UTC</td>
          <td>${esc(f.home)} vs ${esc(f.away)}</td><td>${esc(f.league)}</td><td>${esc(f.status)}</td>
          <td>${f.match_id ? `<span class="pill green">${esc(f.match_id)}</span>` : canAdmin() ? `<div class="actions"><input data-fixture-input="${f.fixture_id}" placeholder="竞彩 match_id" style="width:128px"><button class="btn secondary small" data-fixture-link="${f.fixture_id}">链接</button></div>` : '<span class="status-label">仅 admin 可链接</span>'}</td>
        </tr>`).join("") || '<tr><td colspan="6">暂无 fixture</td></tr>'}
      </tbody></table></div>
    </div>
    <div class="card"><h2 class="card-title">推荐覆盖</h2>
      <div class="status-grid">
        <div class="status-item"><span class="status-label">Snapshots</span><b>${data.recommendations?.snapshots || 0}</b></div>
        <div class="status-item"><span class="status-label">Plans</span><b>${data.recommendations?.plans || 0}</b></div>
        <div class="status-item"><span class="status-label">复核失败</span><b>${data.recommendations?.review_failed || 0}</b></div>
      </div>
    </div>
  `;
  els("[data-fixture-link]").forEach(btn => btn.onclick = async () => {
    const id = btn.dataset.fixtureLink;
    const input = document.querySelector(`[data-fixture-input="${id}"]`);
    try {
      await post("/admin/api/football/link", { fixture_id: Number(id), match_id: input.value.trim() });
      toast("fixture 已链接"); loadOps();
    } catch (error) { toast(error.message, "error"); }
  });
}

async function loadUsers() {
  const root = el("#view-users");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api("/admin/api/users");
  root.innerHTML = `
    <div class="toolbar"><div><h2 style="margin:0">后台账号</h2><div class="card-sub" style="margin:0">viewer 只读 · operator 可复核/发布 · admin 可改模型/账号</div></div><button class="btn primary" id="add-user">创建账号</button></div>
    <div class="table-wrap"><table><thead><tr><th>账号</th><th>角色</th><th>状态</th><th>最近登录</th><th>操作</th></tr></thead><tbody>
      ${data.users.map(u => `<tr>
        <td><b>${esc(u.username)}</b><div class="status-label">#${u.id}</div></td>
        <td><select data-user-role="${u.id}" ${u.username === "admin" ? "disabled" : ""}>${["viewer", "operator", "admin"].map(r => `<option value="${r}" ${u.role === r ? "selected" : ""}>${r}</option>`).join("")}</select></td>
        <td>${u.enabled ? statusPill("ok") : statusPill("muted")}</td>
        <td class="mono">${esc(fmtTime(u.last_login_at, true))}</td>
        <td class="actions">
          <button class="btn secondary small" data-user-pw="${u.id}">重置密码</button>
          <button class="btn ${u.enabled ? "warn" : "primary"} small" data-user-toggle="${u.id}" data-enabled="${u.enabled}">${u.enabled ? "停用" : "启用"}</button>
          <button class="btn danger small" data-user-delete="${u.id}">删除</button>
        </td></tr>`).join("")}
    </tbody></table></div>
  `;
  el("#add-user").onclick = () => openUserModal();
  els("[data-user-role]").forEach(select => select.onchange = async () => {
    try { await patch(`/admin/api/users/${select.dataset.userRole}`, { role: select.value }); toast("角色已更新"); loadUsers(); }
    catch (error) { toast(error.message, "error"); loadUsers(); }
  });
  els("[data-user-toggle]").forEach(btn => btn.onclick = async () => {
    try { await patch(`/admin/api/users/${btn.dataset.userToggle}`, { enabled: btn.dataset.enabled !== "true" }); toast("状态已更新"); loadUsers(); }
    catch (error) { toast(error.message, "error"); }
  });
  els("[data-user-pw]").forEach(btn => btn.onclick = () => openPasswordModal(Number(btn.dataset.userPw)));
  els("[data-user-delete]").forEach(btn => btn.onclick = () => confirmModal("删除账号", "删除后该账号立即失效，确认？", async () => {
    await del(`/admin/api/users/${btn.dataset.userDelete}`); toast("账号已删除"); loadUsers();
  }));
}

function openUserModal() {
  modal("创建后台账号", `
    <form id="user-form" class="form-grid">
      <div><label>用户名</label><input id="uf-username" required></div>
      <div><label>角色</label><select id="uf-role"><option value="viewer">viewer</option><option value="operator" selected>operator</option><option value="admin">admin</option></select></div>
      <div class="full"><label>初始密码（至少 8 位）</label><input id="uf-password" type="password" minlength="8" required></div>
      <div class="actions full"><button class="btn primary" type="submit">创建</button><button class="btn ghost" type="button" id="uf-cancel">取消</button></div>
    </form>`);
  el("#uf-cancel").onclick = closeModal;
  el("#user-form").onsubmit = async event => {
    event.preventDefault();
    try {
      await post("/admin/api/users", { username: el("#uf-username").value,
        password: el("#uf-password").value, role: el("#uf-role").value });
      closeModal(); toast("账号已创建"); loadUsers();
    } catch (error) { toast(error.message, "error"); }
  };
}

function openPasswordModal(id) {
  modal("重置密码", `<form id="pw-form" class="form-grid"><div class="full"><label>新密码（至少 8 位）</label><input id="pw-new" type="password" minlength="8" required></div><div class="actions full"><button class="btn primary" type="submit">更新</button><button class="btn ghost" type="button" id="pw-cancel">取消</button></div></form>`);
  el("#pw-cancel").onclick = closeModal;
  el("#pw-form").onsubmit = async event => {
    event.preventDefault();
    try { await post(`/admin/api/users/${id}/password`, { password: el("#pw-new").value }); closeModal(); toast("密码已重置"); }
    catch (error) { toast(error.message, "error"); }
  };
}

function auditRow(item) {
  const change = item.after ? JSON.stringify(item.after) : item.before ? JSON.stringify(item.before) : "";
  return `<tr><td class="mono">${esc(fmtTime(item.created_at, true))}</td><td>${esc(item.actor)}<div class="status-label">${esc(item.role)}</div></td><td><span class="pill muted">${esc(item.action)}</span></td><td>${esc(item.target_type)}<div class="status-label">${esc(item.target_id)}</div></td><td class="ellipsis mono" title="${esc(change)}">${esc(change)}</td><td class="mono">${esc(item.ip || "—")}</td></tr>`;
}

async function loadAudit() {
  const root = el("#view-audit");
  root.innerHTML = '<div class="skeleton"></div>';
  const data = await api(`/admin/api/audit?limit=100&offset=${state.auditOffset}`);
  const rows = data.items || [];
  root.innerHTML = `
    <div class="card"><div class="toolbar"><div><h2 style="margin:0">管理审计</h2><div class="card-sub" style="margin:0">模型/人设/发布/账号变更留痕</div></div><button class="btn secondary" id="audit-refresh">刷新</button></div>
      <div class="table-wrap"><table><thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>目标</th><th>变更</th><th>IP</th></tr></thead><tbody id="audit-body">
      ${rows.map(auditRow).join("") || '<tr><td colspan="6">暂无审计记录</td></tr>'}
      </tbody></table></div>
      ${data.has_more ? '<div style="text-align:center;margin-top:16px"><button class="btn secondary" id="audit-more">加载更多</button></div>' : ""}
    </div>`;
  el("#audit-refresh").onclick = () => { state.auditOffset = 0; loadAudit(); };
  const more = el("#audit-more");
  if (more) {
    const appendPage = async (button, offset) => {
      button.disabled = true;
      const next = await api(`/admin/api/audit?limit=100&offset=${offset}`);
      el("#audit-body").insertAdjacentHTML("beforeend", (next.items || []).map(auditRow).join(""));
      state.auditOffset = next.next_offset;
      button.remove();
      if (next.has_more) {
        const btn = document.createElement("button");
        btn.className = "btn secondary";
        btn.textContent = "加载更多";
        btn.onclick = () => appendPage(btn, next.next_offset);
        el("#view-audit .card").appendChild(btn);
      }
    };
    more.onclick = () => appendPage(more, data.next_offset);
  }
}

Object.assign(views, {
  ops: { title: "运维", kicker: "系统状态", loader: loadOps },
  users: { title: "账号", kicker: "访问权限", loader: loadUsers },
  audit: { title: "审计", kicker: "操作留痕", loader: loadAudit },
});
