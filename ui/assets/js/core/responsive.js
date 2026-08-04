/* ============================================================
   core/responsive.js · 响应式外壳行为
   - 抽屉菜单（navDrawer 等）开合
   - 全局遮罩 #scrim（是 .drawer 的兄弟节点，避免被抽屉 transform 限制）
   - 底部导航点击、Esc 关闭、遮罩点击关闭
   - 断点检测工具
   主切换点 1024px：以下走移动外壳，以上走桌面外壳。
   ============================================================ */

function isMobile() { return window.matchMedia('(max-width: 1023px)').matches; }

function scrimEl() { return document.getElementById('scrim'); }

function syncScrim() {
  const anyOpen = $$('.drawer.is-open').length > 0;
  const s = scrimEl();
  if (s) s.classList.toggle('is-open', anyOpen);
  document.body.classList.toggle('no-scroll', anyOpen);
}

function openDrawer(id) {
  const d = document.getElementById(id);
  if (!d) return;
  d.classList.add('is-open');
  d.setAttribute('aria-hidden', 'false');
  syncScrim();
  // 焦点移入抽屉，便于键盘 / 读屏用户
  const first = d.querySelector('.drawer-item, [data-close-drawer]');
  if (first) first.focus({ preventScroll: true });
}

function closeDrawer(id) {
  const targets = id
    ? [document.getElementById(id)].filter(Boolean)
    : $$('.drawer.is-open');
  targets.forEach(d => {
    d.classList.remove('is-open');
    d.setAttribute('aria-hidden', 'true');
  });
  syncScrim();
}

function toggleDrawer(id) {
  const d = document.getElementById(id);
  if (!d) return;
  if (d.classList.contains('is-open')) closeDrawer(id);
  else openDrawer(id);
}

// 抽屉内项目点击：切换标签并关闭抽屉
function drawerGoto(name) {
  switchTab(name);
  closeDrawer('navDrawer');
}

// 绑定全局关闭行为（遮罩 / 关闭按钮 / Esc）
function bindShell() {
  const s = scrimEl();
  if (s) s.addEventListener('click', () => closeDrawer());

  $$('.drawer').forEach(d => {
    d.setAttribute('aria-hidden', d.classList.contains('is-open') ? 'false' : 'true');
    const closeBtn = d.querySelector('[data-close-drawer]');
    if (closeBtn) closeBtn.addEventListener('click', () => closeDrawer(d.id));
  });

  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const openDrawerEl = $('.drawer.is-open');
    if (openDrawerEl) { closeDrawer(openDrawerEl.id); return; }
    const openModalEl = $('.modal.is-open');
    if (openModalEl) closeModal(openModalEl.id);
  });

  // 跨过 1024px 断点时，桌面态强制收起抽屉，避免 body 残留 no-scroll
  const mq = window.matchMedia('(min-width: 1024px)');
  const onChange = e => { if (e.matches) closeDrawer(); };
  if (mq.addEventListener) mq.addEventListener('change', onChange);
  else if (mq.addListener) mq.addListener(onChange);
}
