/* ============================================================
   core/theme.js · 主题（暗色模式）与行情配色偏好
   - 暗色模式：data-theme="dark" | "light"
   - 行情配色：A股红涨绿跌（cn） / 全球绿涨红跌（global）
   通过 localStorage 持久化，首屏由 initTheme() 在 <head> 之后尽快调用。
   ============================================================ */
(function () {
  const THEME_KEY = 'zoe_theme';
  const MKT_KEY = 'zoe_market_color';

  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'light';
  }
  function applyTheme(theme) {
    const t = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
    const btn = document.getElementById('themeToggle');
    if (btn) btn.setAttribute('aria-pressed', String(t === 'dark'));
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: t } }));
  }
  function toggleTheme() {
    applyTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }
  function getMarketColor() {
    return document.documentElement.getAttribute('data-market-color') || 'cn';
  }
  function applyMarketColor(mode) {
    const m = mode === 'global' ? 'global' : 'cn';
    document.documentElement.setAttribute('data-market-color', m);
    try { localStorage.setItem(MKT_KEY, m); } catch (e) {}
    const btn = document.getElementById('mktToggle');
    if (btn) btn.setAttribute('aria-pressed', String(m === 'global'));
  }
  function toggleMarketColor() {
    applyMarketColor(getMarketColor() === 'global' ? 'cn' : 'global');
  }
  function initTheme() {
    let t = null;
    try { t = localStorage.getItem(THEME_KEY); } catch (e) {}
    if (!t && window.matchMedia) {
      t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    applyTheme(t || 'light');
    let m = null;
    try { m = localStorage.getItem(MKT_KEY); } catch (e) {}
    applyMarketColor(m || 'cn');
  }

  window.getTheme = getTheme;
  window.applyTheme = applyTheme;
  window.toggleTheme = toggleTheme;
  window.getMarketColor = getMarketColor;
  window.applyMarketColor = applyMarketColor;
  window.toggleMarketColor = toggleMarketColor;
  window.initTheme = initTheme;
})();
