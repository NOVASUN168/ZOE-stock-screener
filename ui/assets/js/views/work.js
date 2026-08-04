/* ============================================================
   views/work.js · 工作台：字段 / 列表 / 详情 / 新增编辑
   ============================================================ */

// ---------- 字段定义（key 必须与 db.py / scoring.py 完全一致） ----------
const GROUPS = [
  { g: "基础", items: [
    { k: "code", l: "股票代码", t: "text", ph: "sh600519" },
    { k: "name", l: "名称", t: "text", ph: "贵州茅台" },
    { k: "industry", l: "行业", t: "text", ph: "消费/白酒" },
    { k: "price", l: "当前价格", t: "number", ph: "1500" },
  ] },
  { g: "基本面(35%)", items: [
    { k: "roe", l: "ROE(%)", t: "number", ph: ">15" },
    { k: "roa", l: "ROA(%)", t: "number", ph: ">8" },
    { k: "rev_growth_years", l: "营收连续增长年数", t: "number", ph: "0-3" },
    { k: "netprofit_growth_years", l: "净利润连续增长年数", t: "number", ph: "0-3" },
    { k: "fcf_positive", l: "自由现金流转正", t: "chk" },
    { k: "debt_ratio", l: "资产负债率(%)", t: "number", ph: "制造<60/科技<50" },
    { k: "sector_type", l: "行业类型", t: "sel", opts: ["制造业", "科技", "金融", "其他"] },
  ] },
  { g: "估值(20%)", items: [
    { k: "pe", l: "PE", t: "number" },
    { k: "pe_industry_avg", l: "行业PE均值", t: "number" },
    { k: "pb", l: "PB", t: "number", ph: "<=3 佳" },
    { k: "peg", l: "PEG", t: "number", ph: "<1.5" },
    { k: "ev_ebitda", l: "EV/EBITDA", t: "number", ph: "<=15" },
    { k: "safety_margin", l: "安全边际(%)", t: "number", ph: ">30" },
  ] },
  { g: "成长(25%)", items: [
    { k: "rd_increase", l: "研发投入持续增加", t: "chk" },
    { k: "mkt_share_growth", l: "市场份额增长", t: "chk" },
    { k: "industry_space", l: "行业空间", t: "sel", opts: ["大", "中", "小"] },
    { k: "moat", l: "护城河", t: "sel", opts: ["明显", "强", "中等", "弱", "无"] },
    { k: "profit_forecast_3y", l: "未来三年利润增速(%)", t: "number" },
  ] },
  { g: "范围与AI分类(V2.0)", items: [
    { k: "market", l: "市场", t: "sel", opts: ["A股", "港股", "A+H"] },
    { k: "board", l: "板块", t: "sel", opts: ["主板", "创业板", "科创板", "北交所", "H股", "红筹", "民营港股"] },
    { k: "ai_category", l: "AI分类", t: "sel", opts: ["核心基础", "模型平台", "AI革命", "AI医药"] },
    { k: "ai_driven", l: "是否AI驱动", t: "sel", opts: ["1", "0"] },
    { k: "research_signals", l: "信息来源信号", t: "text", ph: "公告;产品进展;技术突破;客户采用;产业变化;监管动态" },
  ] },
  { g: "资金(15%·主力长期)", items: [
    { k: "main_force_trend", l: "主力长期趋势", t: "sel", opts: ["流入", "持平", "流出"] },
    { k: "northbound", l: "北向资金", t: "sel", opts: ["增持", "持平", "减持"] },
    { k: "institution_change", l: "机构持仓(10日)", t: "sel", opts: ["增仓", "持平", "减仓"] },
  ] },
  { g: "软风险(5%)", items: [
    { k: "financial_risk", l: "财务风险", t: "chk" },
    { k: "litigation", l: "重大诉讼", t: "chk" },
    { k: "pledge_ratio", l: "质押比例(%)", t: "number" },
    { k: "regulatory_penalty", l: "监管处罚", t: "chk" },
    { k: "goodwill_ratio", l: "商誉占比(%)", t: "number" },
  ] },
  { g: "硬过滤(一票否决)", items: [
    { k: "st_flag", l: "ST股", t: "chk" },
    { k: "delisting_risk", l: "退市风险", t: "chk" },
    { k: "fraud_flag", l: "财务造假嫌疑", t: "chk" },
    { k: "consecutive_loss", l: "连续亏损", t: "chk" },
    { k: "major_holder_reduction", l: "大股东减持", t: "chk" },
    { k: "high_pledge", l: "高质押", t: "chk" },
  ] },
];

const COMPUTED = [
  ["total_score", "综合评分"], ["rating", "评级"], ["recommend_index", "推荐指数"],
  ["risk_flags", "风险标记"], ["reasonable_valuation", "估值看法(推断)"],
  ["suggested_position", "配置视图"], ["expected_hold", "预计持有(长期)"],
  ["core_competence", "核心竞争力(护城河)"], ["long_term_thesis", "长期研究逻辑"],
  ["advantages", "优势"], ["risks_text", "风险提示"], ["recommend_reasons", "推荐理由(4条)"],
];

// ---------- 表单渲染 ----------
function buildForm(data) {
  data = data || {};
  const body = document.getElementById('formBody');
  body.innerHTML = '';
  GROUPS.forEach(grp => {
    const div = document.createElement('div');
    div.className = 'grp';
    div.innerHTML = `<h3>${esc(grp.g)}</h3>`;
    const grid = document.createElement('div');
    grid.className = 'grid';
    grp.items.forEach(it => {
      const f = document.createElement('div');
      const val = data[it.k];
      if (it.t === 'chk') {
        f.className = 'field chk';
        f.innerHTML = `<input type="checkbox" id="f_${it.k}" ${val ? 'checked' : ''}><label for="f_${it.k}">${esc(it.l)}</label>`;
      } else if (it.t === 'sel') {
        const opts = `<option value="">—</option>` + it.opts.map(o => `<option ${val === o ? 'selected' : ''}>${esc(o)}</option>`).join('');
        f.className = 'field';
        f.innerHTML = `<label>${esc(it.l)}</label><select id="f_${it.k}">${opts}</select>`;
      } else {
        f.className = 'field';
        f.innerHTML = `<label>${esc(it.l)}</label><input id="f_${it.k}" type="${it.t}" value="${val != null ? val : ''}" placeholder="${it.ph != null ? esc(it.ph) : ''}">`;
      }
      grid.appendChild(f);
    });
    div.appendChild(grid);
    body.appendChild(div);
  });
}

function collectForm() {
  const d = {};
  GROUPS.forEach(grp => grp.items.forEach(it => {
    if (it.t === 'chk') { d[it.k] = document.getElementById('f_' + it.k).checked ? 1 : 0; }
    else {
      let v = document.getElementById('f_' + it.k).value.trim();
      if (v === '') { d[it.k] = ''; }
      else if (it.t === 'number') { d[it.k] = isNaN(parseFloat(v)) ? '' : parseFloat(v); }
      else { d[it.k] = v; }
    }
  }));
  return d;
}

// ---------- 列表 ----------
function riskHtml(r) {
  return (r.risk_flags && r.risk_flags !== '无')
    ? `<span class="risk">${esc(r.risk_flags)}</span>`
    : `<span class="risk ok">无</span>`;
}

function stockCols() {
  return [
    { label: '⚖', render: r => `<input type="checkbox" class="cmpChk" value="${r.id}">` },
    { label: '代码', render: r => `<code>${esc(r.code || '-')}</code>` },
    { label: '名称', render: r => esc(r.name || '-') },
    { label: '行业', render: r => esc(r.industry || '-') },
    { label: '市场', render: r => esc(r.market || '-') },
    { label: 'AI分类', render: r => `<span class="pill">${esc(r.ai_category || '-')}</span>` },
    { label: '现价', render: r => esc(r.price != null ? r.price : '-') },
    { label: '综合评分', render: r => `<span class="badge ${badgeClass(r.rating || '')}">${(r.total_score || 0).toFixed(1)}</span>` },
    { label: '五维雪花', render: r => `<span title="${esc(r.dim_summary || '')}" onclick="viewDetail(${r.id})">${snowflakeSVG(r, 44, false)}</span>` },
    { label: '评级', render: r => `${(r.rating || '-')} <span class="stars">${esc(r.recommend_index || '')}</span>` },
    { label: '风险标记', render: r => riskHtml(r) },
    { label: '操作', render: r =>
      `<button class="btn-line btn-sm" onclick="viewDetail(${r.id})">查看</button> ` +
      `<button class="btn-line btn-sm" onclick="openEdit(${r.id})">编辑</button> ` +
      `<button class="btn-line btn-sm" style="color:var(--mkt-red)" onclick="del(${r.id})">删除</button>` },
  ];
}

function stockCard(r) {
  return `<div class="dcard">
    <div class="dcard-head">
      <div class="dcard-ident">
        <div class="dcard-name">${esc(r.name || '-')} <span class="dcard-code">${esc(r.code || '-')}</span></div>
        <div class="mini">${esc(r.industry || '-')} · ${esc(r.market || '-')} · <span class="pill">${esc(r.ai_category || '-')}</span></div>
      </div>
      <div class="dcard-aside"><span class="badge ${badgeClass(r.rating || '')}">${(r.total_score || 0).toFixed(1)}</span></div>
    </div>
    <dl class="dcard-kv">
      <div><dt>现价</dt><dd>${esc(r.price != null ? r.price : '-')}</dd></div>
      <div><dt>评级</dt><dd>${(r.rating || '-')} <span class="stars">${esc(r.recommend_index || '')}</span></dd></div>
      <div><dt>风险</dt><dd>${riskHtml(r)}</dd></div>
    </dl>
    <div class="dcard-foot">
      <label class="mini" style="display:flex;align-items:center;gap:4px"><input type="checkbox" class="cmpChk" value="${r.id}"> 对比</label>
      <button class="btn-line btn-sm" onclick="viewDetail(${r.id})">查看</button>
      <button class="btn-line btn-sm" onclick="openEdit(${r.id})">编辑</button>
      <button class="btn-line btn-sm" style="color:var(--mkt-red)" onclick="del(${r.id})">删除</button>
    </div>
  </div>`;
}

async function load() {
  const style = document.getElementById('fStyle').value;
  const ai = document.getElementById('fAi').value;
  const mkt = document.getElementById('fMarket').value;
  const ind = document.getElementById('fIndustry').value.trim();
  const min = document.getElementById('fMin').value.trim();
  let url = '/api/stocks?' + [
    style ? `style=${encodeURIComponent(style)}` : '',
    ai ? `ai_category=${encodeURIComponent(ai)}` : '',
    mkt ? `market=${encodeURIComponent(mkt)}` : '',
    ind ? `industry=${encodeURIComponent(ind)}` : '',
    min ? `min_score=${encodeURIComponent(min)}` : '',
  ].filter(Boolean).join('&');
  const res = await fetch(url);
  const rows = await res.json();
  render(rows);
}

function render(rows) {
  document.getElementById('count').textContent = `共 ${rows.length} 只`;
  SNOW_CACHE = {};
  (rows || []).forEach(r => { if (r.id != null) SNOW_CACHE[r.id] = r; });
  const el = document.getElementById('stockTable');
  renderDataTable(el, {
    columns: stockCols(),
    rows: rows || [],
    renderCard: stockCard,
    emptyText: '暂无股票，点击右上角「＋ 新增股票」开始录入。',
  });
}

// ---------- 详情 ----------
async function viewDetail(id) {
  const res = await fetch('/api/stocks/' + id);
  const r = await res.json();
  document.getElementById('detailTitle').textContent = `${r.name || ''}（${r.code || ''}）`;
  let h = '';
  if (r.dim_fundamental != null) {
    h += `<div class="snowwrap"><div class="snow-figure">${snowflakeSVG(r, 220, true)}</div>${dimBars(r)}</div>`;
    if (r.dim_summary) h += `<div class="snow-summary">🌨 一句话看懂：${esc(r.dim_summary)}（模型推断，非投资建议）</div>`;
  }
  h += `<dl class="detail">`;
  COMPUTED.forEach(([k, label]) => {
    let v = r[k];
    if (v === undefined || v === '') v = '—';
    if (k === 'risk_flags' && v !== '无') v = `<span class="risk">${esc(v)}</span>`;
    if (k === 'recommend_reasons') v = String(v).split('|').map(s => `<span class="pill">${esc(s)}</span>`).join('');
    h += `<dt>${esc(label)}</dt><dd>${v}</dd>`;
  });
  h += `</dl>`;
  const b = document.getElementById('detailBody');
  b.innerHTML = h;
  attachSnowZoom(b);
  openModal('detailModal');
}

// ---------- 新增 / 编辑 ----------
function openAdd() {
  EDIT_ID = null;
  document.getElementById('formTitle').textContent = '新增股票';
  buildForm({});
  openModal('formModal');
}
async function openEdit(id) {
  EDIT_ID = id;
  const res = await fetch('/api/stocks/' + id);
  const r = await res.json();
  document.getElementById('formTitle').textContent = '编辑：' + (r.name || r.code);
  buildForm(r);
  openModal('formModal');
}
async function saveForm() {
  const d = collectForm();
  const opt = { method: EDIT_ID ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) };
  const url = EDIT_ID ? ('/api/stocks/' + EDIT_ID) : '/api/stocks';
  const res = await fetch(url, opt);
  const r = await res.json();
  if (r && (r.id || r.total_score != null)) {
    toast(EDIT_ID ? '已更新并重新评分' : '已新增并评分：' + (r.total_score != null ? r.total_score : ''));
    closeModal('formModal');
    load();
  } else { toast('保存失败：' + (r.error || '未知错误')); }
}
async function del(id) {
  if (!confirm('确认删除该股票？')) return;
  await fetch('/api/stocks/' + id, { method: 'DELETE' });
  toast('已删除');
  load();
}

// ---------- 顶部操作 ----------
async function rescoreAll() { await fetch('/api/rescore', { method: 'POST' }); toast('已重算全部评分'); load(); }
function exportJSON() {
  fetch('/api/stocks').then(r => r.json()).then(rows => {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'stock-screener-export.json';
    a.click();
    toast('已导出 ' + rows.length + ' 条');
  });
}
