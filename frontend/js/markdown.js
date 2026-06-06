/* ═══════════════════════════════════════════
   Markdown — 基于 marked.js 的渲染
   ═══════════════════════════════════════════ */

const Markdown = {
  _ready: false,

  /** 初始化 marked（需要 CDN 加载完成） */
  init() {
    if (typeof marked === 'undefined') {
      console.warn('[Markdown] marked.js not loaded yet, using fallback');
      return;
    }
    marked.setOptions({
      breaks: true,
      gfm: true,
    });
    this._ready = true;
  },

  /** 渲染 Markdown → HTML */
  render(text) {
    if (!text) return '';
    if (this._ready && typeof marked !== 'undefined') {
      try {
        return marked.parse(text);
      } catch (e) {
        console.warn('[Markdown] marked.parse failed, fallback:', e.message);
        return this._fallback(text);
      }
    }
    return this._fallback(text);
  },

  /** 简易 fallback 渲染（marked 还没加载完成时用） */
  _fallback(text) {
    let html = Utils.escapeHtml(text);
    html = html
      // Headers
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Bold
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Bullet lists
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      // Blockquote
      .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
      // Horizontal rules
      .replace(/^---$/gm, '<hr>')
      // Line breaks
      .replace(/\n/g, '<br>');
    return html;
  },
};
