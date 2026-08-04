/* ============================================================
   core/state.js · 全局状态 + 用户 / 权限工具
   state 为单例对象，供各视图读写；getUser/getToken 为函数声明（提升可用）。
   ============================================================ */

let EDIT_ID = null;       // 当前编辑的股票 id（null = 新增）
let LAST_PORT = null;     // 最近一次生成的组合
let SNOW_CACHE = {};      // id -> 股票行（含 dim_* 字段），供迷你图/对比复用
window.__rowCache = [];   // 筛选结果行缓存，供详情弹窗使用

const state = {
  user: getUser(),
  token: getToken(),
  tier: null,            // 'free' | 'premium'
  billing: { enabled: false, mode: 'test', tier: null, expiry: null },  // 来自 /api/billing/status
  catalog: [],
  schemes: [],
  currentScheme: null,   // {id,name,description,is_shared,is_pinned,...}
  conditions: [],        // 编辑器条件 [{catalog_key,operator,value,value2,enabled,_meta}]
  dirty: false,
};

// ---------- 凭证 ----------
function getToken() { return localStorage.getItem('zoe_token'); }
function getUser() {
  try { return JSON.parse(localStorage.getItem('zoe_user') || 'null'); } catch (e) { return null; }
}

// ---------- 权限 ----------
function roleRank(role) { return { viewer: 1, editor: 2, admin: 3, owner: 4 }[role] || 0; }
function isLoggedIn() { return !!state.user; }
function canEdit() { return isLoggedIn() && roleRank(state.user.role) >= 2; }       // editor+
function canAdmin() { return isLoggedIn() && (state.user.role === 'admin' || state.user.role === 'owner'); }
function canOwner() { return isLoggedIn() && state.user.role === 'owner'; }
function roleLabel(r) { return { owner: '拥有者', admin: '管理员', editor: '编辑', viewer: '只读' }[r] || r; }
function tierLabel() { return state.tier === 'premium' ? 'premium' : 'free'; }
