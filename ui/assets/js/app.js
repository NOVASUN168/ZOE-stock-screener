/* ============================================================
   app.js · 入口：事件绑定 + 初始化
   在所有模块之后加载，确保全局函数均已就绪。
   ============================================================ */

// 工作台：移动端筛选方案三栏分段切换
function switchWorkbenchPane(name) {
  $$('.workbench > .wb-pane').forEach(p => p.classList.toggle('is-shown', p.dataset.pane === name));
  $$('.segmented button').forEach(b => b.classList.toggle('is-active', b.dataset.pane === name));
}

function bindEvents() {
  // 工作台
  const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
  bind('btnAdd', openAdd);
  bind('btnAddMobile', openAdd);
  bind('btnRescore', rescoreAll);
  bind('btnRescoreMobile', rescoreAll);
  bind('btnExport', exportJSON);
  bind('btnExportMobile', exportJSON);
  bind('formCancel', () => closeModal('formModal'));
  bind('formSave', saveForm);
  bind('detailClose', () => closeModal('detailModal'));
  bind('btnCompare', openCompare);
  bind('compareClose', () => closeModal('compareModal'));
  bind('btnFilter', load);
  bind('btnReset', () => {
    const s = document.getElementById('fStyle'); if (s) s.value = '';
    const ai = document.getElementById('fAi'); if (ai) ai.value = '';
    const m = document.getElementById('fMarket'); if (m) m.value = '';
    const ind = document.getElementById('fIndustry'); if (ind) ind.value = '';
    const mn = document.getElementById('fMin'); if (mn) mn.value = '';
    load();
  });
  // 桌面标签栏
  $$('.tab').forEach(t => t.onclick = () => switchTab(t.dataset.tab));
  // 底部导航
  $$('.bnav-item').forEach(b => { if (b.dataset.tab) b.addEventListener('click', () => switchTab(b.dataset.tab)); });
  // 抽屉触发
  $$('[data-drawer]').forEach(b => b.addEventListener('click', () => {
    const id = b.dataset.drawer;
    if (id) toggleDrawer(id); else closeDrawer('navDrawer');
  }));
  // 抽屉内导航项
  $$('.drawer [data-tab]').forEach(b => b.addEventListener('click', () => drawerGoto(b.dataset.tab)));

  // 预警
  bind('btnAddAlert', addAlert);
  // 组合
  bind('btnSavePort', savePortfolio);
  bind('btnRefreshReview', loadReview);
  $$('[data-ptype]').forEach(b => b.onclick = () => loadPortfolio(b.dataset.ptype));

  // 筛选方案
  bind('btnNewScheme', newScheme);
  bind('btnSaveScheme', saveScheme);
  bind('btnSnapScheme', snapshotScheme);
  bind('btnApplyScheme', applyScheme);
  bind('btnPinScheme', () => pinScheme(!(state.currentScheme && state.currentScheme.is_pinned)));
  bind('btnDelScheme', deleteScheme);
  bind('btnExportScheme', exportScheme);
  bind('btnPullScheme', pullScheme);
  bind('catSearch', null);
  const cs = document.getElementById('catSearch'); if (cs) cs.oninput = renderCatalog;
  // 方案三栏分段
  $$('.segmented button').forEach(b => b.addEventListener('click', () => switchWorkbenchPane(b.dataset.pane)));

  // 登录 / 账户
  bind('loginClose', closeLogin);
  bind('loginBtn', doLogin);
  bind('licBtn', activateLicense);
  bind('btnAccActivate', activateFromAccount);
}

function init() {
  initTheme();
  bindShell();
  bindModals();
  bindEvents();
  renderUserBox();
  restoreSession();
  load();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
