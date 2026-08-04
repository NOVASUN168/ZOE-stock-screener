/* ============================================================
   core/responsive.js · 响应式外壳行为
   - 抽屉菜单（navDrawer / filterDrawer）开合
   - 底部导航点击、Esc 关闭、遮罩点击关闭
   - 断点检测工具
   主切换点 1024px：以下走移动外壳，以上走桌面外壳。
   ============================================================ */

function isMobile() { return window.matchMedia('(max-width: 1023px)').matches; }

function openDrawer(id) {
  const d = document.getElementById(id);
  if (!d) return;
  d.classList.add('is-open');
  const scrim = d.querySelector('.scrim');
  if (scrim) scrim.classList.add('is-open');
  document.body.classList.add('no-scroll');
}
function closeDrawer(id) {
  if (id) {
    const d = document.getElementById(id);
    if (d) { d.classList.remove('is-open'); const s = d.querySelector('.scrim'); if (s) s.classList.remove('is-open'); }
  } else {
    $$('.drawer.is-open').forEach(d => { d.classList.remove('is-open'); const s = d.querySelector('.scrim'); if (s) s.classList.remove('is-open'); });
  }
  if (!$$('.drawer.is-open').length) document.body.classList.remove('no-scroll');
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
  $$('.drawer').forEach(d => {
    const scrim = d.querySelector('.scrim');
    if (scrim) scrim.addEventListener('click', () => closeDrawer(d.id));
    const closeBtn = d.querySelector('[data-close-drawer]');
    if (closeBtn) closeBtn.addEventListener('click', () => closeDrawer(d.id));
    // 抽屉内的导航项
    d.querySelectorAll('[data-tab]').forEach(b => {
      b.addEventListener('click', () => drawerGoto(b.dataset.tab));
    });
  });
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const openDrawerEl = $('.drawer.is-open');
    if (openDrawerEl) { closeDrawer(openDrawerEl.id); return; }
    const openModal = $('.modal.is-open, .modal.open');
    if (openModal) closeModal(openModal.id);
  });
}
