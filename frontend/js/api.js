/* ═══════════════════════════════════════════
   API — 后端接口封装
   依赖: Utils
   ═══════════════════════════════════════════ */

const API = {
  BASE: 'http://localhost:8000',

  /** 健康检查 */
  async health() {
    const r = await fetch(`${this.BASE}/api/health`);
    return r.ok;
  },

  /** 发送消息 — 返回 ReadableStream reader */
  async sendMessage(question, sessionId = 'default') {
    const r = await fetch(`${this.BASE}/api/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionId, category: null }),
    });
    if (!r.ok) throw new Error(`API error ${r.status}: ${r.statusText}`);
    return r.body.getReader();
  },

  /** 清除会话 */
  async clearSession(sessionId) {
    if (sessionId === 'default') return;
    await fetch(`${this.BASE}/api/chat/session/${sessionId}`, { method: 'DELETE' });
  },

  /** 文档列表 */
  async listDocuments() {
    const r = await fetch(`${this.BASE}/api/documents/list`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  /** 摄入状态 */
  async ingestionStatus() {
    const r = await fetch(`${this.BASE}/api/documents/status`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  /** 摄入单篇 */
  async ingestDocument(filePath, category = 'General', force = false) {
    const r = await fetch(`${this.BASE}/api/documents/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath, category, force }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },

  /** 删除文档 */
  async deleteDocument(fileName) {
    const r = await fetch(`${this.BASE}/api/documents/${encodeURIComponent(fileName)}`, {
      method: 'DELETE',
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },

  /** 全量重摄入 */
  async reingestAll() {
    const r = await fetch(`${this.BASE}/api/documents/reingest-all`, { method: 'POST' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
};
