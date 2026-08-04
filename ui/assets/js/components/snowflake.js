/* ============================================================
   components/snowflake.js · 五维雪花图（借鉴 Simply Wall St）
   SVG 用 viewBox + width:100% 自适应；移动端支持捏合/滚轮缩放。
   ============================================================ */

const DIMS = [
  { k: 'dim_fundamental', l: '基本面' },
  { k: 'dim_valuation', l: '估值' },
  { k: 'dim_growth', l: '成长' },
  { k: 'dim_capital', l: '资金' },
  { k: 'dim_safety', l: '安全' },
];

function snowColor(score) {
  if (score >= 80) return '#16a34a';      // 优：绿（与评级徽章一致）
  if (score >= 65) return '#0ea5e9';      // 良：蓝
  if (score >= 50) return '#d97706';      // 中：琥珀
  return '#dc2626';                       // 弱：红
}

function snowPoints(row, cx, cy, r) {
  return DIMS.map((d, i) => {
    const pct = Math.max(0, Math.min(100, Number(row[d.k]) || 0));
    const ang = -Math.PI / 2 + i * 2 * Math.PI / 5;
    const rr = r * (0.08 + 0.92 * pct / 100);
    return [cx + rr * Math.cos(ang), cy + rr * Math.sin(ang)];
  });
}

function gridPentagon(cx, cy, r) {
  const pts = DIMS.map((d, i) => {
    const ang = -Math.PI / 2 + i * 2 * Math.PI / 5;
    return `${cx + r * Math.cos(ang)},${cy + r * Math.sin(ang)}`;
  }).join(' ');
  return `<polygon points="${pts}" fill="none" stroke="var(--line)" stroke-width="1"/>`;
}

function snowflakeSVG(row, size, withLabels) {
  const pad = withLabels ? 30 : 2;
  const cx = size / 2, cy = size / 2, r = size / 2 - pad;
  const color = snowColor(Number(row.total_score) || 0);
  let h = `<svg class="${withLabels ? 'snow-fig' : 'minisnow'}" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">`;
  [1, 0.66, 0.33].forEach(f => { h += gridPentagon(cx, cy, r * f); });
  DIMS.forEach((d, i) => {
    const ang = -Math.PI / 2 + i * 2 * Math.PI / 5;
    h += `<line x1="${cx}" y1="${cy}" x2="${cx + r * Math.cos(ang)}" y2="${cy + r * Math.sin(ang)}" stroke="var(--line)" stroke-width="1"/>`;
    if (withLabels) {
      const lx = cx + (r + 16) * Math.cos(ang), ly = cy + (r + 16) * Math.sin(ang);
      h += `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="12" fill="var(--text-muted)">${d.l}</text>`;
    }
  });
  const pts = snowPoints(row, cx, cy, r).map(p => p.join(',')).join(' ');
  h += `<polygon points="${pts}" fill="${color}" fill-opacity="0.28" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>`;
  if (withLabels) {
    snowPoints(row, cx, cy, r).forEach(p => { h += `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="${color}"/>`; });
  }
  h += `</svg>`;
  return h;
}

function dimBars(row) {
  return `<div class="dimbars">` + DIMS.map(d => {
    const pct = Math.max(0, Math.min(100, Number(row[d.k]) || 0));
    const lv = pct >= 80 ? '优秀' : pct >= 60 ? '良好' : pct >= 40 ? '一般' : '偏弱';
    const c = pct >= 80 ? '#16a34a' : pct >= 60 ? '#0ea5e9' : pct >= 40 ? '#d97706' : '#dc2626';
    return `<div class="dimrow"><span class="dl">${d.l}</span>
      <span class="track"><span class="fill" style="width:${pct}%;background:${c}"></span></span>
      <span class="dv" style="color:${c}">${pct} · ${lv}</span></div>`;
  }).join('') + `</div>`;
}

function openCompare() {
  const ids = Array.prototype.slice.call(document.querySelectorAll('.cmpChk:checked')).map(c => Number(c.value));
  if (ids.length < 2 || ids.length > 3) { toast('请勾选 2-3 只股票再对比'); return; }
  const rows = ids.map(id => SNOW_CACHE[id]).filter(Boolean);
  if (rows.length < 2) { toast('数据缺失，请刷新列表'); return; }
  const colors = ['#2563eb', '#d97706', '#16a34a'];
  const size = 300, pad = 34, cx = size / 2, cy = size / 2, r = size / 2 - pad;
  let svg = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="display:block;margin:0 auto">`;
  [1, 0.66, 0.33].forEach(f => { svg += gridPentagon(cx, cy, r * f); });
  DIMS.forEach((d, i) => {
    const ang = -Math.PI / 2 + i * 2 * Math.PI / 5;
    svg += `<line x1="${cx}" y1="${cy}" x2="${cx + r * Math.cos(ang)}" y2="${cy + r * Math.sin(ang)}" stroke="var(--line)"/>`;
    const lx = cx + (r + 18) * Math.cos(ang), ly = cy + (r + 18) * Math.sin(ang);
    svg += `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="13" fill="var(--text-muted)">${d.l}</text>`;
  });
  rows.forEach((row, i) => {
    const pts = snowPoints(row, cx, cy, r).map(p => p.join(',')).join(' ');
    svg += `<polygon points="${pts}" fill="${colors[i]}" fill-opacity="0.18" stroke="${colors[i]}" stroke-width="2" stroke-linejoin="round"/>`;
  });
  svg += `</svg>`;
  let legend = `<div class="cmp-legend">` + rows.map((row, i) =>
    `<span><span class="cmp-dot" style="background:${colors[i]}"></span>${esc(row.name || row.code)}（${(row.total_score || 0).toFixed(1)}分）</span>`).join('') + `</div>`;
  let tbl = `<table class="table"><thead><tr><th>维度</th>` + rows.map(rw => `<th>${esc(rw.name || rw.code)}</th>`).join('') + `</tr></thead><tbody>`;
  DIMS.forEach(d => {
    const vals = rows.map(rw => Number(rw[d.k]) || 0);
    const best = Math.max.apply(null, vals);
    tbl += `<tr><td>${d.l}</td>` + vals.map(v => `<td ${v === best ? 'style="color:#16a34a;font-weight:700"' : ''}>${v}</td>`).join('') + `</tr>`;
  });
  tbl += `<tr><td><b>综合评分</b></td>` + rows.map(rw => `<td><b>${(rw.total_score || 0).toFixed(1)}</b></td>`).join('') + `</tr></tbody></table>`;
  document.getElementById('compareBody').innerHTML = svg + legend + tbl +
    `<div class="mini" style="margin-top:10px">绿色数字 = 该维度领先。雪花越大越圆润，代表五个维度越均衡优秀（评分为模型推断，非投资建议）。</div>`;
  openModal('compareModal');
}

/* ---------- 移动端缩放（捏合 / 滚轮 / 双击复位） ---------- */
function attachSnowZoom(root) {
  const fig = root.querySelector('.snow-figure');
  if (!fig) return;
  const svg = fig.querySelector('svg');
  if (!svg) return;
  svg.style.transformOrigin = 'center center';
  let scale = 1, startDist = 0, startScale = 1;

  function apply() {
    svg.style.transform = scale > 1.01 ? 'scale(' + scale + ')' : 'none';
    fig.classList.toggle('is-zoomed', scale > 1.01);
  }
  function dist(t) {
    return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
  }

  fig.addEventListener('wheel', e => {
    e.preventDefault();
    scale = Math.min(4, Math.max(1, scale + (e.deltaY < 0 ? 0.25 : -0.25)));
    apply();
  }, { passive: false });

  fig.addEventListener('touchstart', e => {
    if (e.touches.length === 2) { startDist = dist(e.touches); startScale = scale; }
  }, { passive: true });

  fig.addEventListener('touchmove', e => {
    if (e.touches.length === 2 && startDist > 0) {
      e.preventDefault();
      scale = Math.min(4, Math.max(1, startScale * (dist(e.touches) / startDist)));
      apply();
    }
  }, { passive: false });

  fig.addEventListener('dblclick', () => { scale = 1; apply(); });
}
