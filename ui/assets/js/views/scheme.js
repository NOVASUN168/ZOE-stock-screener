/* ============================================================
   views/scheme.js · 筛选方案 / 条件编辑器 / 版本 / 用户管理
   ============================================================ */

async function loadSchemeTab() {
  if (!isLoggedIn()) { renderSchemeLocked(); return; }
  await Promise.all([loadCatalog(), loadSchemes(), loadOpLogs()]);
  renderEditorButtons();
}
function renderSchemeLocked() {
  document.getElementById('catalogBody').innerHTML = `<div class="empty">请先登录以使用筛选方案（右上角「登录」）。</div>`;
  document.getElementById('schemeList').innerHTML = '';
  document.getElementById('condList').innerHTML = '';
  document.getElementById('screenResult').innerHTML = '';
  document.getElementById('versionList').innerHTML = '';
  document.getElementById('opLogList').innerHTML = '';
  renderEditorButtons();
}
const OP_LABELS = { gt: '大于', lt: '小于', between: '介于', eq: '等于', neq: '不等于', in: '属于', like: '包含' };
const OP_BY_FTYPE = { numeric: ['gt', 'lt', 'between', 'eq'], enum: ['in', 'eq', 'neq'], bool: ['eq'] };
function defaultOp(ftype) { return (OP_BY_FTYPE[ftype] && OP_BY_FTYPE[ftype][0]) || 'eq'; }

async function loadCatalog() {
  const { res, data } = await api('GET', '/api/filter-catalog');
  if (res.ok) state.catalog = data || [];
  renderCatalog();
}
function renderCatalog() {
  const body = document.getElementById('catalogBody');
  const q = (document.getElementById('catSearch').value || '').trim().toLowerCase();
  const order = ['财务', '估值', '资金', '技术', '题材', '风险'];
  const groups = {};
  (state.catalog || []).forEach(it => {
    if (q && !((it.name || '').toLowerCase().includes(q))) return;
    (groups[it.grp] = groups[it.grp] || []).push(it);
  });
  let html = '';
  order.concat(Object.keys(groups).filter(g => !order.includes(g))).forEach(g => {
    const items = groups[g];
    if (!items || !items.length) return;
    html += `<div class="catalog-grp"><h4>${esc(g)}</h4>`;
    items.forEach(it => {
      const locked = it.is_premium === 1 || it.is_premium === '1';
      const unit = it.unit ? ('（' + esc(it.unit) + '）') : '';
      const lock = locked ? ` <span class="lock">🔒 需授权</span>` : '';
      html += `<div class="cat-item ${locked ? 'locked' : ''}" onclick="addCondition('${esc(it.key)}')">
        <div class="cn">${esc(it.name)}${lock}</div>
        <div class="cu">${unit} <code>${esc(it.key)}</code> · ${esc(it.ftype)}</div>
        ${it.description ? `<div class="cd">${esc(it.description)}</div>` : ''}
      </div>`;
    });
    html += `</div>`;
  });
  body.innerHTML = html || `<div class="mini">无匹配条件。</div>`;
}
function catalogItem(key) { return (state.catalog || []).find(it => it.key === key); }
function enumVals(meta) {
  let e = meta.enum_values;
  if (Array.isArray(e)) return e.map(String);
  if (typeof e === 'string' && e) return e.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  return [];
}
function addCondition(key) {
  const meta = catalogItem(key);
  if (!meta) { toast('目录未加载，请刷新'); return; }
  const op = meta.operator || defaultOp(meta.ftype);
  const c = { catalog_key: key, operator: op, value: '', value2: '', enabled: true, _meta: meta };
  if (meta.ftype === 'enum') { const ev = enumVals(meta); if (ev.length) c.value = ev[0]; }
  if (meta.ftype === 'bool') { c.value = '1'; }
  state.conditions.push(c);
  state.dirty = true;
  renderConditions();
  renderEditorButtons();
}
function renderConditions() {
  const el = document.getElementById('condList');
  if (!state.conditions.length) { el.innerHTML = `<div class="mini">尚未添加条件。点击左侧目录项加入。</div>`; return; }
  el.innerHTML = state.conditions.map((c, idx) => {
    const m = c._meta || catalogItem(c.catalog_key) || {};
    const locked = m.is_premium === 1 || m.is_premium === '1';
    const ops = (OP_BY_FTYPE[m.ftype] || ['eq']).map(o => `<option value="${o}" ${c.operator === o ? 'selected' : ''}>${OP_LABELS[o] || o}</option>`).join('');
    let valHtml = '';
    if (m.ftype === 'enum') {
      const opts = enumVals(m).map(v => `<option value="${esc(v)}" ${String(c.value) === String(v) ? 'selected' : ''}>${esc(v)}</option>`).join('');
      valHtml = `<select data-cidx="${idx}" data-cfield="value">${opts}</select>`;
    } else if (m.ftype === 'bool') {
      valHtml = `<select data-cidx="${idx}" data-cfield="value">
        <option value="1" ${c.value === '1' ? 'selected' : ''}>是</option>
        <option value="0" ${c.value !== '1' ? 'selected' : ''}>否</option></select>`;
    } else {
      if (c.operator === 'between') {
        valHtml = `<input type="number" data-cidx="${idx}" data-cfield="value" value="${esc(c.value)}" placeholder="最小">
          <span>~</span>
          <input type="number" data-cidx="${idx}" data-cfield="value2" value="${esc(c.value2)}" placeholder="最大">`;
      } else {
        valHtml = `<input type="number" data-cidx="${idx}" data-cfield="value" value="${esc(c.value)}" placeholder="数值">`;
      }
    }
    return `<div class="cond-row">
      <div class="cr-top">
        <span class="cr-name">${esc(m.name || c.catalog_key)}</span>
        ${locked ? `<span class="lock">🔒</span>` : ''}
        <span class="cu">${m.unit ? esc(m.unit) : ''}</span>
        <span class="spacer" style="flex:1"></span>
        <label class="mini"><input type="checkbox" data-cidx="${idx}" data-cfield="enabled" ${c.enabled ? 'checked' : ''}> 启用</label>
        <button class="btn-danger btn-sm" onclick="removeCondition(${idx})">删除</button>
      </div>
      <div class="cr-vals">
        <select data-cidx="${idx}" data-cfield="operator" onchange="onOpChange(${idx},this.value)">${ops}</select>
        ${valHtml}
      </div>
    </div>`;
  }).join('');
}
function onOpChange(idx, newOp) {
  state.conditions = readConditionsFromDOM();
  state.conditions[idx].operator = newOp;
  state.dirty = true;
  renderConditions();
  renderEditorButtons();
}
function removeCondition(idx) { state.conditions.splice(idx, 1); state.dirty = true; renderConditions(); renderEditorButtons(); }
function readConditionsFromDOM() {
  return state.conditions.map((c, idx) => {
    const m = c._meta || catalogItem(c.catalog_key) || {};
    const op = document.querySelector(`[data-cidx="${idx}"][data-cfield="operator"]`);
    let value = '', value2 = '';
    if (m.ftype === 'enum' || m.ftype === 'bool') {
      const v = document.querySelector(`[data-cidx="${idx}"][data-cfield="value"]`);
      value = v ? v.value : '';
    } else {
      const v1 = document.querySelector(`[data-cidx="${idx}"][data-cfield="value"]`);
      const v2 = document.querySelector(`[data-cidx="${idx}"][data-cfield="value2"]`);
      value = v1 ? v1.value : '';
      value2 = v2 ? v2.value : '';
    }
    const en = document.querySelector(`[data-cidx="${idx}"][data-cfield="enabled"]`);
    return { catalog_key: c.catalog_key, operator: op ? op.value : c.operator, value, value2, enabled: en ? en.checked : true };
  });
}
function cleanCondForSend(c) {
  const m = catalogItem(c.catalog_key) || {};
  const out = { catalog_key: c.catalog_key, operator: c.operator, value: c.value, value2: c.value2, enabled: c.enabled };
  if (m.ftype === 'numeric') {
    out.value = (c.value === '' || c.value == null) ? null : parseFloat(c.value);
    out.value2 = (c.operator === 'between') ? ((c.value2 === '' || c.value2 == null) ? null : parseFloat(c.value2)) : null;
  }
  return out;
}
async function loadSchemes() {
  const { res, data } = await api('GET', '/api/schemes');
  if (res.ok) state.schemes = data || [];
  renderSchemeList();
}
function renderSchemeList() {
  const el = document.getElementById('schemeList');
  if (!state.schemes.length) { el.innerHTML = `<div class="mini">暂无方案。点击「＋ 新建方案」。</div>`; return; }
  el.innerHTML = state.schemes.map(s => {
    const active = (state.currentScheme && state.currentScheme.id === s.id) ? 'active' : '';
    const pin = s.is_pinned ? '⭐' : '';
    const share = s.is_shared ? '🔗' : '';
    return `<div class="scheme-card ${active}" onclick="openScheme(${s.id})">
      <div class="sc-name">${pin} ${esc(s.name)} ${share}</div>
      <div class="sc-meta">所有者：${esc(s.owner_name || s.owner || '-')} · 条件 ${Array.isArray(s.conditions) ? s.conditions.length : 0}</div>
    </div>`;
  }).join('');
}
async function openScheme(id) {
  const { res, data } = await api('GET', '/api/schemes/' + id);
  if (!res.ok) { toast('加载方案失败'); return; }
  state.currentScheme = { id, name: data.name, description: data.description, is_shared: !!data.is_shared, is_pinned: !!data.is_pinned };
  state.conditions = (data.conditions || []).map(c => {
    const meta = catalogItem(c.catalog_key) || {};
    return { catalog_key: c.catalog_key, operator: c.operator, value: c.value != null ? c.value : '', value2: c.value2 != null ? c.value2 : '', enabled: c.enabled !== 0 && c.enabled !== false, _meta: meta };
  });
  state.dirty = false;
  document.getElementById('schemeName').value = data.name || '';
  document.getElementById('schemeDesc').value = data.description || '';
  document.getElementById('schemeShared').checked = !!data.is_shared;
  document.getElementById('screenResult').innerHTML = '';
  renderSchemeList();
  renderConditions();
  renderEditorButtons();
  await loadVersions(id);
}
function newScheme() {
  state.currentScheme = null;
  state.conditions = [];
  state.dirty = false;
  document.getElementById('schemeName').value = '';
  document.getElementById('schemeDesc').value = '';
  document.getElementById('schemeShared').checked = false;
  document.getElementById('screenResult').innerHTML = '';
  document.getElementById('versionList').innerHTML = '';
  renderSchemeList();
  renderConditions();
  renderEditorButtons();
}
async function saveScheme() {
  if (!canEdit()) { toast('无权限（需 editor 及以上）'); return; }
  const name = document.getElementById('schemeName').value.trim();
  const description = document.getElementById('schemeDesc').value.trim();
  const is_shared = document.getElementById('schemeShared').checked ? 1 : 0;
  if (!name) { toast('请填写方案名'); return; }
  const conditions = readConditionsFromDOM().map(cleanCondForSend);
  if (state.currentScheme && state.currentScheme.id) {
    const { res, data } = await api('PUT', '/api/schemes/' + state.currentScheme.id, { name, description, is_shared, conditions });
    if (res.ok) { toast('已更新并自动快照'); state.dirty = false; await loadSchemes(); }
    else toast('保存失败：' + (data && data.error || res.status));
  } else {
    const { res, data } = await api('POST', '/api/schemes', { name, description, is_shared, conditions });
    if (res.ok) { state.currentScheme = { id: data.id, name, description, is_shared }; state.dirty = false; toast('已新建并自动快照'); await loadSchemes(); await loadVersions(data.id); }
    else toast('新建失败：' + (data && data.error || res.status));
  }
}
async function deleteScheme() {
  if (!state.currentScheme || !state.currentScheme.id) { toast('未选中方案'); return; }
  if (!confirm('确认删除该方案？')) return;
  const { res, data } = await api('DELETE', '/api/schemes/' + state.currentScheme.id);
  if (res.ok) { toast('已删除'); newScheme(); await loadSchemes(); }
  else toast('删除失败：' + (data && data.error || res.status));
}
async function pinScheme(pinned) {
  if (!state.currentScheme || !state.currentScheme.id) { toast('未选中方案'); return; }
  if (!canEdit()) { toast('无权限'); return; }
  const { res, data } = await api('POST', '/api/schemes/' + state.currentScheme.id + '/pin', { pinned });
  if (res.ok) { toast(pinned ? '已置顶' : '已取消置顶'); await loadSchemes(); }
  else toast('操作失败：' + (data && data.error || res.status));
}
async function snapshotScheme() {
  if (!state.currentScheme || !state.currentScheme.id) { toast('请先保存方案再快照'); return; }
  if (!canEdit()) { toast('无权限'); return; }
  const note = prompt('快照备注（可选）：', '') || '';
  const { res, data } = await api('POST', '/api/schemes/' + state.currentScheme.id + '/snapshot', { note });
  if (res.ok) { toast('已快照'); await loadVersions(state.currentScheme.id); }
  else toast('快照失败：' + (data && data.error || res.status));
}
async function applyScheme() {
  if (!state.conditions.length) { toast('请先添加筛选条件'); return; }
  const body = (state.dirty || !state.currentScheme || !state.currentScheme.id)
    ? { conditions: readConditionsFromDOM().map(cleanCondForSend) }
    : { scheme_id: state.currentScheme.id };
  try {
    const { res, data } = await api('POST', '/api/screen', body);
    if (res.status === 402) {
      const key = (data && data.condition) ? `<code>${esc(data.condition)}</code>` : '<b>付费条件</b>';
      const b = await loadBilling();
      const enabled = (b && b.enabled);
      const billingHtml = enabled
        ? `<button class="btn-line btn-sm" onclick="openCheckout()">💳 前往订阅</button>`
        : `<button class="btn-line btn-sm" disabled title="在线订阅未开启">💳 前往订阅（未开启）</button> <span class="mini">在线订阅未开启</span>`;
      document.getElementById('screenResult').innerHTML =
        `<div class="paywall">🔒 此筛选含 ${key}，请激活授权码或使用在线订阅解锁后重试：
          <div style="margin-top:10px;display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap">
            <div class="field" style="flex:1;min-width:200px"><label>离线激活码</label><input id="payLic" placeholder="ZOE-PREMIUM-xxxx"></div>
            <button class="btn-line btn-sm" onclick="activateLicense(document.getElementById('payLic').value)">激活</button>
            ${billingHtml}
          </div>
          <div class="mini" style="margin-top:6px">订阅 / 账户页可查看完整订阅状态与到期日。</div>
        </div>`;
      return;
    }
    if (!res.ok) { toast('筛选失败：' + (data && data.error || res.status)); return; }
    renderScreenResults(data.results || []);
  } catch (e) { /* 401/403 已由 api 处理 */ }
}
function renderScreenResults(rows) {
  const el = document.getElementById('screenResult');
  if (!rows.length) { el.innerHTML = `<div class="empty">未命中任何股票。</div>`; return; }
  window.__rowCache = [];
  let h = `<div class="mini">共命中 ${rows.length} 只</div><div class="table-scroll"><table class="table"><thead><tr><th>代码</th><th>名称</th><th>行业</th><th>评分</th><th>评级</th><th>风险</th><th></th></tr></thead><tbody>`;
  rows.forEach(r => {
    window.__rowCache.push(r);
    const idx = window.__rowCache.length - 1;
    const risk = (r.risk_flags && r.risk_flags !== '无') ? `<span class="risk">${esc(r.risk_flags)}</span>` : `<span class="risk ok">无</span>`;
    h += `<tr><td><code>${esc(r.code || '-')}</code></td><td>${esc(r.name || '-')}</td><td>${esc(r.industry || '-')}</td>
      <td><span class="badge ${badgeClass(r.rating || '')}">${(r.total_score != null ? r.total_score : 0).toFixed(1)}</span></td>
      <td>${esc(r.rating || '-')}</td><td>${risk}</td>
      <td><button class="btn-line btn-sm" onclick="showRowDetail(${idx})">详情</button></td></tr>`;
  });
  h += `</tbody></table></div>`;
  el.innerHTML = h;
}
function showRowDetail(idx) {
  const r = window.__rowCache[idx];
  if (!r) return;
  document.getElementById('detailTitle').textContent = `${r.name || ''}（${r.code || ''}）`;
  let h = `<dl class="detail">`;
  Object.keys(r).forEach(k => {
    let v = r[k];
    if (v === undefined || v === '') v = '—';
    if (k === 'risk_flags' && v !== '无') v = `<span class="risk">${esc(v)}</span>`;
    h += `<dt>${esc(k)}</dt><dd>${typeof v === 'object' ? esc(JSON.stringify(v)) : v}</dd>`;
  });
  h += `</dl>`;
  document.getElementById('detailBody').innerHTML = h;
  openModal('detailModal');
}
async function loadVersions(id) {
  const { res, data } = await api('GET', '/api/schemes/' + id + '/versions');
  const el = document.getElementById('versionList');
  if (!res.ok) { el.innerHTML = `<div class="mini">版本加载失败</div>`; return; }
  if (!data.length) { el.innerHTML = `<div class="mini">暂无版本快照。</div>`; return; }
  el.innerHTML = data.map(v => `<div class="vrow">
    <b>v${esc(v.version_no)}</b> <span class="mini">${esc(v.created_at || '')}</span>
    <span class="mini">${esc(v.created_by || '')}</span>
    <span class="mini">${esc(v.note || '')}</span>
    <span class="spacer" style="flex:1"></span>
    ${canEdit() ? `<button class="btn-line btn-sm" onclick="rollbackVersion(${v.id})">↩ 回滚</button>` : ''}
  </div>`).join('');
}
async function rollbackVersion(vid) {
  if (!state.currentScheme || !state.currentScheme.id) return;
  if (!canEdit()) { toast('无权限'); return; }
  if (!confirm('确认回滚到该版本？')) return;
  const { res, data } = await api('POST', '/api/schemes/' + state.currentScheme.id + '/rollback', { version_id: vid });
  if (res.ok) { toast('已回滚'); await openScheme(state.currentScheme.id); }
  else toast('回滚失败：' + (data && data.error || res.status));
}
async function exportScheme() {
  if (!state.currentScheme || !state.currentScheme.id) { toast('未选中方案'); return; }
  if (!canEdit()) { toast('无权限'); return; }
  const { res, data } = await api('POST', '/api/schemes/' + state.currentScheme.id + '/export');
  if (res.ok) { toast('已导出并提交 git：' + (data.git || '')); }
  else toast('导出失败：' + (data && data.error || res.status));
}
async function pullScheme() {
  if (!state.currentScheme || !state.currentScheme.id) { toast('未选中方案'); return; }
  if (!canEdit()) { toast('无权限'); return; }
  const { res, data } = await api('POST', '/api/schemes/' + state.currentScheme.id + '/pull');
  if (res.ok) { toast('已拉取：' + String(data.output || '').slice(0, 80)); await openScheme(state.currentScheme.id); }
  else toast('拉取失败：' + (data && data.error || res.status));
}
async function loadOpLogs() {
  const el = document.getElementById('opLogList');
  try {
    const { res, data } = await api('GET', '/api/operation-logs');
    if (!res.ok) { el.innerHTML = `<div class="mini">日志加载失败</div>`; return; }
    if (!data.length) { el.innerHTML = `<div class="mini">暂无操作日志。</div>`; return; }
    let h = `<table class="table logtbl"><thead><tr><th>时间</th><th>用户</th><th>动作</th><th>对象</th><th>详情</th></tr></thead><tbody>`;
    data.slice(0, 100).forEach(l => {
      h += `<tr><td>${esc(l.created_at || '')}</td><td>${esc(l.user_id || '')}</td><td>${esc(l.action || '')}</td>
        <td>${esc((l.target_type || '') + '#' + (l.target_id || ''))}</td><td class="mini">${esc(l.detail || '')}</td></tr>`;
    });
    h += `</tbody></table>`;
    el.innerHTML = h;
  } catch (e) { }
}
async function loadUsers() {
  const el = document.getElementById('userTableBody');
  if (!el) return;
  const { res, data } = await api('GET', '/api/users');
  if (!res.ok) { el.innerHTML = `<tr><td colspan="4">加载失败</td></tr>`; return; }
  el.innerHTML = data.map(u => `<tr>
    <td>${esc(u.display_name || u.username)}<br><span class="mini">${esc(u.username)}</span></td>
    <td>${roleLabel(u.role)}</td>
    <td>${esc(u.sub_tier || '-')}</td>
    <td>${canOwner() ? `<select data-uid="${u.id}" onchange="changeRole(${u.id},this.value)">${['viewer', 'editor', 'admin', 'owner'].map(r => `<option ${u.role === r ? 'selected' : ''}>${r}</option>`).join('')}</select>` : roleLabel(u.role)}</td>
  </tr>`).join('');
}
function renderUserMgmt() {
  const card = document.getElementById('userMgmt');
  if (!canAdmin()) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  if (!document.getElementById('userTableBody')) {
    card.innerHTML = `<h3>👥 用户管理</h3>
      <div class="inline-form">
        <div class="field"><label>新用户名</label><input id="nuUser" placeholder="username"></div>
        <div class="field"><label>密码</label><input id="nuPass" type="password" placeholder="password"></div>
        <div class="field"><label>显示名</label><input id="nuName" placeholder="显示名"></div>
        <div class="field"><label>角色</label><select id="nuRole"><option>viewer</option><option>editor</option><option>admin</option><option>owner</option></select></div>
        <button class="btn-primary btn-sm" id="nuAdd">＋ 新建用户</button>
      </div>
      <table class="table logtbl"><thead><tr><th>用户</th><th>角色</th><th>套餐</th><th>操作</th></tr></thead><tbody id="userTableBody"></tbody></table>`;
    document.getElementById('nuAdd').onclick = addUser;
  }
  loadUsers();
}
async function addUser() {
  if (!canAdmin()) { toast('无权限'); return; }
  const username = document.getElementById('nuUser').value.trim();
  const password = document.getElementById('nuPass').value;
  const display_name = document.getElementById('nuName').value.trim();
  const role = document.getElementById('nuRole').value;
  if (!username || !password) { toast('请填写用户名和密码'); return; }
  const { res, data } = await api('POST', '/api/users', { username, password, display_name, role });
  if (res.ok) { toast('已新建用户'); document.getElementById('nuUser').value = ''; document.getElementById('nuPass').value = ''; document.getElementById('nuName').value = ''; loadUsers(); }
  else toast('新建失败：' + (data && data.error || res.status));
}
async function changeRole(id, role) {
  if (!canOwner()) { toast('仅拥有者可修改他人角色'); await loadUsers(); return; }
  const { res, data } = await api('PUT', '/api/users/' + id, { role });
  if (res.ok) { toast('已更新角色'); }
  else { toast('更新失败：' + (data && data.error || res.status)); await loadUsers(); }
}
function renderEditorButtons() {
  const editable = canEdit();
  ['btnSaveScheme', 'btnSnapScheme', 'btnPinScheme', 'btnDelScheme', 'btnExportScheme', 'btnPullScheme', 'btnNewScheme'].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.disabled = !editable;
  });
  const applyB = document.getElementById('btnApplyScheme');
  if (applyB) applyB.disabled = !isLoggedIn();
}
