/* ============================================================
   views/alerts.js · 预警·风控
   ============================================================ */

const ALERT_TYPES = { score_drop: '评分跌破', price_up: '价格涨破', price_down: '价格跌破', risk_trigger: '出现风险标记' };

async function loadAlertTab() {
  // 风控提醒
  const rr = await fetch('/api/risk-reminders');
  const risks = await rr.json();
  const rl = document.getElementById('riskList');
  if (!risks.length) rl.innerHTML = `<div class="mini">✅ 当前无风险标记股票。</div>`;
  else rl.innerHTML = risks.map(x =>
    `<div class="risk-banner"><b>${esc(x.stock.name)}</b> （${esc(x.stock.code)}）— ${esc(x.flags)} ${x.hard ? '<b>· 已一票否决</b>' : ''}</div>`
  ).join('');
  // 股票下拉
  const sr = await fetch('/api/stocks');
  const stocks = await sr.json();
  document.getElementById('alertStock').innerHTML = stocks.map(s => `<option value="${s.id}">${esc(s.name)}（${esc(s.code)}）</option>`).join('');
  await loadAlerts();
}

async function loadAlerts() {
  const ar = await fetch('/api/alerts');
  const alerts = await ar.json();
  const al = document.getElementById('alertList');
  if (!alerts.length) { al.innerHTML = `<div class="mini">暂无预警规则，上方添加一条。</div>`; return; }
  al.innerHTML = alerts.map(x => {
    const tg = x.triggered ? `<span class="trig">已触发 · ${esc(x.reason)}</span>` : `<span class="idle">未触发</span>`;
    const th = x.alert.threshold != null ? `阈值 ${esc(x.alert.threshold)}` : '';
    return `<div class="alert-row">
      <b>${esc(x.stock.name)}</b> · ${ALERT_TYPES[x.alert.atype] || esc(x.alert.atype)} ${th}
      ${tg} <span class="mini">${esc(x.alert.note || '')}</span>
      <span class="spacer" style="flex:1"></span>
      <button class="btn-danger btn-sm" onclick="delAlert(${x.alert.id})">删除</button>
    </div>`;
  }).join('');
}

async function addAlert() {
  const stock_id = document.getElementById('alertStock').value;
  const atype = document.getElementById('alertType').value;
  const threshold = document.getElementById('alertThreshold').value.trim();
  const note = document.getElementById('alertNote').value.trim();
  if (!stock_id) { toast('请先选择股票'); return; }
  const body = { stock_id: Number(stock_id), atype, note };
  if (atype !== 'risk_trigger' && threshold !== '') body.threshold = parseFloat(threshold);
  await fetch('/api/alerts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  document.getElementById('alertThreshold').value = '';
  document.getElementById('alertNote').value = '';
  toast('已添加预警');
  await loadAlerts();
}

async function delAlert(id) {
  await fetch('/api/alerts/' + id, { method: 'DELETE' });
  toast('已删除');
  await loadAlerts();
}
