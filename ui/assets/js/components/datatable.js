/* ============================================================
   components/datatable.js · 表格 ↔ 卡片 双端渲染
   同一份数据，桌面渲染真表格（横向滚动兜底），移动端渲染卡片列表。
   满足"表格在移动端转为卡片式"的要求，且只维护一处逻辑。
   ============================================================ */

function renderDataTable(el, cfg) {
  if (!el) return;
  const { columns, rows, renderCard, emptyText } = cfg;
  if (!rows || !rows.length) {
    el.innerHTML =
      `<div class="state"><div class="state-icon">📭</div>` +
      `<div class="state-msg">${esc(emptyText || '暂无数据')}</div></div>`;
    return;
  }

  // 桌面：真表格（容器 .table-scroll 提供横向滚动兜底）
  let table = '<div class="table-scroll only-desktop"><table class="table"><thead><tr>';
  (columns || []).forEach(c => {
    const align = c.align ? ` style="text-align:${c.align}"` : '';
    table += `<th class="${c.cls || ''}"${align}>${esc(c.label)}</th>`;
  });
  table += '</tr></thead><tbody>';
  rows.forEach((r, idx) => {
    table += '<tr>';
    (columns || []).forEach(c => {
      const v = c.render ? c.render(r, idx) : esc(r[c.key]);
      const align = c.align ? ` style="text-align:${c.align}"` : '';
      table += `<td class="${c.cls || ''}"${align}>${v}</td>`;
    });
    table += '</tr>';
  });
  table += '</tbody></table></div>';

  // 移动端：卡片列表
  let cards = '<div class="dcard-list only-mobile">';
  rows.forEach((r, idx) => {
    cards += renderCard
      ? renderCard(r, idx)
      : `<div class="dcard">${(columns || []).map(c =>
          `<div class="dcard-row"><span class="dk">${esc(c.label)}</span><span class="dv">${c.render ? c.render(r, idx) : esc(r[c.key])}</span></div>`
        ).join('')}</div>`;
  });
  cards += '</div>';

  el.innerHTML = table + cards;
}
