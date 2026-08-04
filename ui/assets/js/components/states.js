/* ============================================================
   components/states.js · 状态占位：加载 / 空 / 错误 / 骨架屏
   统一的状态组件，避免各页面各自为政。
   ============================================================ */

function renderState(el, opts) {
  if (!el) return;
  opts = opts || {};
  const type = opts.type || 'empty';
  if (type === 'loading') {
    el.innerHTML = `<div class="state"><div class="spinner"></div><div class="state-msg">${esc(opts.text || '加载中…')}</div></div>`;
  } else if (type === 'error') {
    el.innerHTML =
      `<div class="state is-error"><div class="state-icon">⚠️</div>` +
      `<div class="state-msg">${esc(opts.text || '出错了，请稍后重试')}</div>` +
      (opts.action ? `<button class="btn-line btn-sm" onclick="${opts.action}">重试</button>` : '') +
      `</div>`;
  } else {
    el.innerHTML =
      `<div class="state"><div class="state-icon">${opts.icon || '📭'}</div>` +
      `<div class="state-msg">${esc(opts.text || '暂无数据')}</div></div>`;
  }
}

// 骨架屏：用于首屏/异步加载占位
function skeletonRows(el, count, cols) {
  if (!el) return;
  let h = '<div class="skeleton-wrap">';
  for (let i = 0; i < (count || 3); i++) {
    h += '<div class="skeleton-row">';
    for (let j = 0; j < (cols || 4); j++) {
      h += `<span class="skeleton" style="width:${40 + Math.round(Math.random() * 45)}%"></span>`;
    }
    h += '</div>';
  }
  el.innerHTML = h + '</div>';
}
