/* ============================================================
   views/review.js · 每日复盘
   ============================================================ */

async function loadReview() {
  const r = await fetch('/api/review');
  const d = await r.json();
  let h = `<div class="card"><h3>🟢 买点信号（${d.buy.length}）</h3>`;
  h += d.buy.length
    ? d.buy.map(b => `<div class="alert-row"><b>${esc(b.stock.name)}</b> · ${b.reasons.map(esc).join(' / ')}</div>`).join('')
    : `<div class="mini">暂无明确买点。</div>`;
  h += `</div>`;
  h += `<div class="card"><h3>🔴 卖点信号（${d.sell.length}）</h3>`;
  h += d.sell.length
    ? d.sell.map(s => `<div class="alert-row"><b>${esc(s.stock.name)}</b> · ${s.reasons.map(esc).join(' / ')}</div>`).join('')
    : `<div class="mini">暂无明确卖点。</div>`;
  h += `</div>`;
  h += `<div class="card"><h3>⚠️ 风险警示（${d.risks.length}）</h3>`;
  h += d.risks.length
    ? d.risks.map(x => `<div class="risk-banner"><b>${esc(x.stock.name)}</b> — ${esc(x.flags)}</div>`).join('')
    : `<div class="mini">暂无风险警示。</div>`;
  h += `</div>`;
  h += `<div class="card"><h3>🔥 市场热点 / 行业轮动</h3><div class="kv">`;
  (d.rotation || []).forEach(x => { h += `<div><b>${esc(x.avg_score)}</b><span>${esc(x.industry)} · ${x.count}只</span></div>`; });
  h += `</div><div class="mini" style="margin-top:8px">热点行业：${(d.hot_topics || []).map(h => h.industry).map(esc).join('、')}</div></div>`;
  h += `<div class="card"><h3>📌 明日重点关注</h3>`;
  h += d.tomorrow_focus.length
    ? d.tomorrow_focus.map(f => `<div class="alert-row">${esc(f)}</div>`).join('')
    : `<div class="mini">暂无。</div>`;
  h += `</div>`;
  document.getElementById('reviewBody').innerHTML = h;
}
