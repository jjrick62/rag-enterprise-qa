/* ═══════════════════════════════════════════
   Utils — 工具函数，无依赖
   ═══════════════════════════════════════════ */

const Utils = {
  /** HTML 转义 */
  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  /** 生成短 UUID */
  uuid() {
    return 'xxxx-xxxx-xxxx'.replace(/x/g, () =>
      Math.floor(Math.random() * 16).toString(16)
    );
  },

  /** 格式化 ISO 时间为可读字符串 */
  formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} `
      + `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  },

  /** 防抖 */
  debounce(fn, ms = 300) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  },

  /** 截断文本 */
  truncate(str, maxLen = 60) {
    if (!str) return '';
    return str.length <= maxLen ? str : str.slice(0, maxLen - 3) + '...';
  },

  /** 百分比格式化 */
  pct(val) {
    return Math.round(val * 100);
  },
};
