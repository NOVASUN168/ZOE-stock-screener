/* ============================================================
   core/dom.js · DOM 工具 + 全局通用函数
   保留原 index.html 中的全局函数名（toast / esc / switchTab / badgeClass），
   并新增 $ / $$ 选择器，供所有模块复用。
   ============================================================ */

// 选择器简写
function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

// HTML 转义（防 XSS）
function esc(s) {
  return (s == null ? "" : String(s)).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// 轻提示（单实例复用，移动端自动贴近底部安全区）
let _toastTimer = null;
function toast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}

// 评级徽章配色类（语义色，独立于行情涨跌色）
function badgeClass(rating) {
  if (!rating) return 'b-no';
  if (rating.indexOf('强烈推荐') >= 0) return 'b-strong';
  if (rating.indexOf('推荐') >= 0) return 'b-rec';
  if (rating.indexOf('关注') >= 0) return 'b-watch';
  if (rating.indexOf('排除') >= 0) return 'b-excl';
  if (rating.indexOf('一般') >= 0) return 'b-ok';
  return 'b-no';
}

// 切换标签：同时驱动桌面标签栏(.tab)、移动端底部导航(.bnav-item)、面板(.panel)
// 同一 data-tab 在两端共用，保证改一处两端同时生效
function switchTab(name) {
  $$('.tab').forEach(t => t.classList.toggle('is-active', t.dataset.tab === name));
  $$('.bnav-item').forEach(b => b.classList.toggle('is-active', b.dataset.tab === name));
  $$('.panel').forEach(s => s.classList.toggle('is-active', s.id === 'panel-' + name));
  closeDrawer();
  if (name === 'alert') loadAlertTab();
  if (name === 'port') { /* 等待用户点类型 */ }
  if (name === 'review') loadReview();
  if (name === 'scheme') loadSchemeTab();
  if (name === 'account') loadAccountTab();
  if (name === 'pricing') loadPricingTab();
  // 滚动回顶部，移动端体验更佳
  const main = document.querySelector('.app-main');
  if (main) main.scrollTo ? main.scrollTo({ top: 0, behavior: 'smooth' }) : window.scrollTo(0, 0);
}
