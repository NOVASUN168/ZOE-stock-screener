/* ============================================================
   views/portfolio.js · 组合推荐
   ============================================================ */

async function loadPortfolio(ptype) {
  const r = await fetch('/api/portfolio?ptype=' + ptype);
  const g = await r.json();
  LAST_PORT = { ptype, name: g.name, picks: g.picks };
  let h = `<div class="kv">
    <div><b>${esc(g.risk_level)}</b><span>风险等级</span></div>
    <div><b>${esc(g.alloc_view || '-')}</b><span>配置视图</span></div>
    <div><b>${esc(g.max_drawdown)}</b><span>最大回撤(推断)</span></div>
    <div><b>${esc(g.avg_score)}</b><span>组合均分</span></div>
    <div><b>${esc(g.count)}</b><span>持仓数</span></div>
  </div>`;
  h += `<div class="table-scroll"><table class="table"><thead><tr><th>名称</th><th>行业</th><th>评分</th><th>配置</th><th>配置视图</th><th>持有(长期)</th><th>风险标记</th></tr></thead><tbody>`;
  (g.picks || []).forEach(p => {
    const rf = (p.risk_flags && p.risk_flags !== '无') ? `<span class="risk">${esc(p.risk_flags)}</span>` : `<span class="risk ok">无</span>`;
    h += `<tr><td>${esc(p.name)}</td><td>${esc(p.industry || '-')}</td><td>${esc(p.score)}</td><td><b>${esc(p.alloc_pct)}%</b></td><td>${esc(p.suggested_position || '-')}</td><td>${esc(p.expected_hold || '-')}</td><td>${rf}</td></tr>`;
  });
  h += `</tbody></table></div>`;
  h += `<div class="mini" style="margin-top:10px">行业占比：` + Object.entries(g.industry_pct || {}).map(([k, v]) => `${esc(k)} ${v}%`).join(' · ') + `</div>`;
  h += `<div class="note" style="margin-top:8px">${esc(g.note || '')}</div>`;
  document.getElementById('portBody').innerHTML = h;
  document.getElementById('btnSavePort').style.display = 'inline-block';
}

async function savePortfolio() {
  if (!LAST_PORT) { toast('请先生成组合'); return; }
  await fetch('/api/portfolio/save', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ptype: LAST_PORT.ptype, name: LAST_PORT.name, picks: LAST_PORT.picks, note: '' }),
  });
  toast('已保存组合：' + LAST_PORT.name);
}
