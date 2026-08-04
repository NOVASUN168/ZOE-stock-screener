/* ============================================================
   views/account.js · 订阅 / 账户 / 定价
   ============================================================ */

async function loadBillingSafe() { return loadBilling(); }

async function loadAccountTab() {
  const b = await loadBilling();
  renderBilling(b);
}
async function loadPricingTab() {
  try {
    const { res, data } = await api('GET', '/api/pricing');
    if (!res.ok || !data) return;
    if (data.trial_label) {
      const tl = document.getElementById('trialLabel');
      if (tl) tl.textContent = data.trial_label;
    }
    const plans = (data.plans || []);
    const member = plans.find(p => p.id === 'member');
    const pro = plans.find(p => p.id === 'pro');
    if (member && member.price) { const m = document.getElementById('planMemberPrice'); if (m) m.textContent = member.price; }
    if (pro && pro.price) { const p = document.getElementById('planProPrice'); if (p) p.textContent = pro.price; }
  } catch (e) { /* 静默：用静态默认值 */ }
}
function renderBilling(b) {
  const tierEl = document.getElementById('billingTier');
  const expEl = document.getElementById('billingExpiry');
  const modeEl = document.getElementById('billingMode');
  const btn = document.getElementById('btnCheckout');
  const hint = document.getElementById('checkoutHint');
  if (!tierEl) return;
  tierEl.textContent = (b && b.tier === 'premium') ? '高级版' : '免费版';
  expEl.textContent = (b && b.expiry) ? b.expiry : '未设置';
  modeEl.textContent = (b && b.mode) ? (b.mode === 'live' ? '正式' : '测试') : '—';
  if (b && b.enabled) { btn.disabled = false; btn.onclick = openCheckout; hint.textContent = ''; }
  else { btn.disabled = true; btn.onclick = null; hint.textContent = '在线订阅未开启'; }
}
async function activateFromAccount() {
  const el = document.getElementById('accLicKey');
  const key = el ? el.value.trim() : '';
  if (!key) { toast('请输入激活码'); return; }
  await activateLicense(key);
  await loadBilling();
  renderBilling(state.billing);
  if (el) el.value = '';
}
