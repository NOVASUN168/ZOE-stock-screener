/* ============================================================
   views/auth.js · 登录态 / 用户菜单 / 授权码 / 订阅
   ============================================================ */

function renderUserBox() {
  const box = document.getElementById('userBox');
  const u = state.user;
  if (!u) {
    if (box) box.innerHTML = `<button class="btn-primary btn-sm" onclick="openLogin()">登录</button>`;
    const m = document.getElementById('mobileUserSlot');
    if (m) m.innerHTML = `<button class="drawer-item" onclick="openLogin()"><span class="di-ico">👤</span>登录 / 注册</button>`;
    return;
  }
  const html =
    `<div class="uibadge">👤 ${esc(u.display_name || u.username)} · ${roleLabel(u.role)} · <span id="tierTag">${tierLabel()}</span></div>
     <button class="btn-ghost btn-sm" onclick="toggleUserMenu()">▼</button>
     <div class="umenu" id="userMenu" style="display:none">
       <label>🔓 激活授权码（解锁付费条件）</label>
       <input id="licKey2" placeholder="ZOE-PREMIUM-xxxx">
       <button class="btn-line btn-sm" id="licBtn2">激活授权</button>
       <hr>
       <button onclick="doLogout()">退出登录</button>
     </div>`;
  if (box) box.innerHTML = html;
  const licBtn = document.getElementById('licBtn2');
  if (licBtn) licBtn.onclick = activateLicense;

  const m = document.getElementById('mobileUserSlot');
  if (m) {
    m.innerHTML =
      `<div class="drawer-section">
        <div class="drawer-label">账户</div>
        <div class="uibadge" style="background:var(--bg-sunken);color:var(--text-primary)">👤 ${esc(u.display_name || u.username)} · ${roleLabel(u.role)} · ${tierLabel()}</div>
        <div class="field" style="margin-top:8px"><label>激活授权码</label><input id="licKeyMobile" placeholder="ZOE-PREMIUM-xxxx"></div>
        <button class="btn-line btn-sm" style="width:100%;margin-top:6px" onclick="activateLicense(document.getElementById('licKeyMobile').value)">激活授权</button>
        <button class="btn-ghost btn-sm" style="width:100%;margin-top:6px" onclick="doLogout()">退出登录</button>
      </div>`;
  }
}
function toggleUserMenu() {
  const m = document.getElementById('userMenu');
  if (m) m.style.display = (m.style.display === 'none' || !m.style.display) ? 'block' : 'none';
}
async function refreshLicense() {
  try {
    const { res, data } = await api('GET', '/api/license/status');
    if (res.ok && data) state.tier = data.tier || state.tier;
  } catch (e) { }
  const tag = document.getElementById('tierTag');
  if (tag) tag.textContent = tierLabel();
}
async function restoreSession() {
  const tk = getToken();
  if (!tk) { renderUserBox(); return; }
  try {
    const { res, data } = await api('GET', '/api/auth/me');
    if (res.ok) { state.user = data.user; localStorage.setItem('zoe_user', JSON.stringify(data.user)); }
  } catch (e) { /* api 已处理 401 */ }
  await refreshLicense();
  renderUserBox();
}
function openLogin(msg) {
  if (msg) toast(msg);
  const u = document.getElementById('loginUser');
  const p = document.getElementById('loginPass');
  const k = document.getElementById('licKey');
  if (u) u.value = '';
  if (p) p.value = '';
  if (k) k.value = '';
  openModal('loginModal');
}
function closeLogin() { closeModal('loginModal'); }
async function doLogin() {
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  if (!username || !password) { toast('请输入用户名和密码'); return; }
  try {
    const res = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
    const d = await res.json();
    if (res.ok) {
      localStorage.setItem('zoe_token', d.token);
      localStorage.setItem('zoe_user', JSON.stringify(d.user));
      state.user = d.user; state.token = d.token;
      closeLogin();
      renderUserBox();
      await refreshLicense();
      if (document.getElementById('panel-scheme').classList.contains('is-active')) loadSchemeTab();
      toast('登录成功：' + (d.user.display_name || d.user.username));
    } else { toast('登录失败：' + (d.error || '401')); }
  } catch (e) { toast('登录请求失败'); }
}
async function doLogout() {
  try { await fetch('/api/auth/logout', { method: 'POST', headers: { 'Authorization': 'Bearer ' + getToken() } }); } catch (e) { }
  localStorage.removeItem('zoe_token');
  localStorage.removeItem('zoe_user');
  state.user = null; state.token = null; state.tier = null; state.currentScheme = null; state.conditions = []; state.dirty = false;
  renderUserBox();
  toast('已退出登录');
  if (document.getElementById('panel-scheme').classList.contains('is-active')) loadSchemeTab();
}
async function activateLicense(key) {
  if (!key) {
    let k = ((document.getElementById('licKey2') || {}).value || '').trim();
    if (!k) { const el = document.getElementById('licKey'); k = el ? el.value.trim() : ''; }
    key = k;
  }
  if (!key) { toast('请输入授权码'); return; }
  try {
    const { res, data } = await api('POST', '/api/license/activate', { key });
    if (res.ok) { state.tier = data.tier || 'premium'; await refreshLicense(); renderUserBox(); toast('授权已激活：' + (data.tier || 'premium') + (data.expiry ? ' · 至 ' + data.expiry : '')); }
    else { toast('激活失败：' + ((data && data.error) || res.status)); }
  } catch (e) { }
}
async function openCheckout(plan) {
  try {
    const p = plan || 'premium_monthly';
    const { res, data } = await api('POST', '/api/billing/checkout', { plan: p });
    if (res.ok && data && data.ok && data.checkout_url) { window.open(data.checkout_url, '_blank'); }
    else if (data && data.error === 'billing_not_configured') { toast('商家尚未开启在线订阅，可使用下方激活码'); }
    else { toast('无法发起订阅：' + ((data && data.error) || res.status)); }
  } catch (e) { }
}
