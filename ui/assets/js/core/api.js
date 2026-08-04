/* ============================================================
   core/api.js · 统一请求封装 + 订阅状态
   自动带 Bearer；401 清凭证并跳登录；403 提示无权限。
   ============================================================ */

async function api(method, path, body) {
  const opt = { method, headers: {} };
  const tk = getToken();
  if (tk) opt.headers['Authorization'] = 'Bearer ' + tk;
  if (body !== undefined) {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(body);
  }
  const res = await fetch(path, opt);
  let data = null;
  try { const t = await res.text(); data = t ? JSON.parse(t) : null; } catch (e) { data = null; }

  if (res.status === 401) {
    localStorage.removeItem('zoe_token');
    localStorage.removeItem('zoe_user');
    state.user = null;
    state.token = null;
    if (typeof renderUserBox === 'function') renderUserBox();
    openLogin('登录已失效或未完成，请重新登录');
    const e = new Error('unauthorized'); e.status = 401; throw e;
  }
  if (res.status === 403) {
    toast('无权限：当前角色（' + (state.user ? roleLabel(state.user.role) : '未登录') + '）不可执行该操作');
    const e = new Error('forbidden'); e.status = 403; throw e;
  }
  return { res, data };
}

// 拉取订阅状态（失败静默，用默认值）
async function loadBilling() {
  try {
    const { res, data } = await api('GET', '/api/billing/status');
    if (res.ok && data) state.billing = data;
  } catch (e) { /* 401/403 已由 api 处理 */ }
  return state.billing;
}
