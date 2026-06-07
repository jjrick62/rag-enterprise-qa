/* ═══════════════════════════════════════════
   App — 应用主入口、标签切换、健康检查
   依赖: Utils, API, Chat, Documents, Toast
   ═══════════════════════════════════════════ */

const App = {
  /** ── 初始化 ── */
  async init() {
    // 初始化 Toast
    Toast.init();

    // 初始化子模块
    Chat.init();
    Documents.init();

    // 标签切换
    this._bindTabs();

    // 健康检查
    await this._checkHealth();
    this._healthTimer = setInterval(() => this._checkHealth(), 15000);

    // 加载初始标签数据
    this.switchTab('chat');
  },

  /** ── 标签切换 ── */
  _bindTabs() {
    document.querySelectorAll('.rail-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this.switchTab(tab.dataset.tab);
      });
    });
  },

  /** ── 切换到指定标签 ── */
  switchTab(name) {
    // 更新标签高亮
    document.querySelectorAll('.rail-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.tab === name);
    });
    // 切换面板
    document.querySelectorAll('.tab-panel').forEach(p => {
      p.classList.toggle('active', p.id === `tab-${name}`);
    });

    // 按需加载
    if (name === 'documents') {
      Documents.load();
    }
  },

  /** ── 健康检查 ── */
  async _checkHealth() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    try {
      const ok = await API.health();
      if (ok) {
        dot.classList.remove('off');
        text.textContent = '后端在线';
      } else {
        dot.classList.add('off');
        text.textContent = '后端异常';
      }
    } catch {
      dot.classList.add('off');
      text.textContent = '后端离线';
    }
  },
};

// Toast 通知工具
const Toast = {
  _container: null,

  init() {
    this._container = document.getElementById('toast-container');
    if (!this._container) {
      this._container = document.createElement('div');
      this._container.id = 'toast-container';
      this._container.className = 'toast-container';
      document.body.appendChild(this._container);
    }
  },

  /** 显示通知 */
  show(message, type = 'info') {
    if (!this._container) this.init();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    this._container.appendChild(el);
    // 4 秒后自动清除
    setTimeout(() => {
      if (el.parentNode) el.remove();
    }, 4000);
  },
};

// ── 启动 ──
document.addEventListener('DOMContentLoaded', () => App.init());
