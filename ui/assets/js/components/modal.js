/* ============================================================
   components/modal.js · 弹窗开合工具
   统一使用 .is-open 状态类（components.css 已定义）。
   ============================================================ */

function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('is-open');
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('is-open');
}

// 一次性绑定：点击遮罩 / 关闭按钮 关闭弹窗
function bindModals() {
  $$('.modal').forEach(m => {
    // 点击遮罩本身（非 .sheet 内容）关闭
    m.addEventListener('click', e => { if (e.target === m) m.classList.remove('is-open'); });
    // 带 data-close 的按钮
    m.querySelectorAll('[data-close]').forEach(b => {
      b.addEventListener('click', () => m.classList.remove('is-open'));
    });
  });
}
