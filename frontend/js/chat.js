/* ═══════════════════════════════════════════
   Chat — 对话界面、SSE 流、多轮会话管理
   依赖: Utils, API, Markdown
   ═══════════════════════════════════════════ */

const Chat = {
  /** 当前活跃的会话 ID */
  activeSession: 'default',

  /** 本地会话存储（key → {id, title, createdAt, messages[]}） */
  sessions: {},

  /** 是否正在生成 */
  streaming: false,

  /** DOM 引用（init 时填充） */
  el: {},

  /** ── 预设问题 ── */
  PRESETS: [
    { q: 'What foundation models are available in watsonx.ai ?', tag: 'models' },
    { q: 'What tuning parameters are available for IBM foundation models?', tag: 'tuning' },
    { q: 'What are tokens and tokenization?', tag: 'basics' },
    { q: 'What is the workflow for a Federated Learning experiment?', tag: 'fedlearn' },
    { q: 'What is the retrieval-augmented generation pattern?', tag: 'rag' },
    { q: 'How do I delete a deployment using the Python client?', tag: 'deploy' },
    { q: 'What is "greedy decoding"?', tag: 'decoding' },
    { q: 'How to build reusable prompts?', tag: 'prompts' },
    { q: 'What is the "random seed" parameter?', tag: 'tuning' },
    { q: '有哪些基础模型可以用？', tag: 'CN→EN' },
    { q: '联邦学习咋回事？', tag: 'CN→EN' },
    { q: '怎么部署模型？', tag: 'CN→EN' },
    { q: '数据库怎么连？', tag: 'CN→EN' },
    { q: 'How do I create a connection to Microsoft SQL Server?', tag: 'db' },
    { q: 'What are the key functions of the geospatial library?', tag: 'geo' },
  ],

  /** ── 初始化 ── */
  init() {
    // 引用 DOM 节点
    this.el = {
      convList: document.getElementById('conv-list'),
      presetList: document.getElementById('preset-list'),
      chatMessages: document.getElementById('chat-messages'),
      chatInput: document.getElementById('chat-input'),
      sendBtn: document.getElementById('send-btn'),
    };

    // 加载本地会话
    this._loadSessions();
    // 渲染预设
    this._renderPresets();
    // 渲染会话列表
    this._renderConvList();
    // 切换到上次活跃会话或 default
    this._restoreActiveSession();
    // 事件绑定
    this._bindEvents();

    // 如果 marked 已经可用马上初始化
    Markdown.init();
  },

  /** ── 本地存储操作 ── */
  _storageKey: 'rag_qa_conversations',

  _loadSessions() {
    try {
      const raw = localStorage.getItem(this._storageKey);
      this.sessions = raw ? JSON.parse(raw) : {};
    } catch {
      this.sessions = {};
    }
  },

  _saveSessions() {
    try {
      // 只保留最近 30 个会话
      const keys = Object.keys(this.sessions);
      if (keys.length > 30) {
        keys.sort((a, b) =>
          (this.sessions[b].createdAt || 0) - (this.sessions[a].createdAt || 0)
        );
        const toDelete = keys.slice(30);
        toDelete.forEach(k => delete this.sessions[k]);
      }
      localStorage.setItem(this._storageKey, JSON.stringify(this.sessions));
    } catch (e) {
      console.warn('[Chat] localStorage 写入失败', e);
    }
  },

  /** ── 渲染预设问题 ── */
  _renderPresets() {
    this.el.presetList.innerHTML = '';
    this.PRESETS.forEach(p => {
      const chip = document.createElement('button');
      chip.className = 'preset-chip';
      chip.innerHTML = `<span class="preset-tag">${p.tag}</span>${Utils.escapeHtml(p.q)}`;
      chip.addEventListener('click', () => {
        this.el.chatInput.value = p.q;
        this._send();
      });
      this.el.presetList.appendChild(chip);
    });
  },

  /** ── 渲染会话列表 ── */
  _renderConvList() {
    this.el.convList.innerHTML = '';
    const ids = Object.keys(this.sessions).sort(
      (a, b) => (this.sessions[b].createdAt || 0) - (this.sessions[a].createdAt || 0)
    );

    ids.forEach(id => {
      const s = this.sessions[id];
      const item = document.createElement('button');
      item.className = 'conv-item' + (id === this.activeSession ? ' active' : '');
      item.innerHTML = `
        <span class="conv-title">${Utils.escapeHtml(s.title || '新对话')}</span>
        <span class="conv-delete" data-id="${id}" title="删除">✕</span>
      `;
      item.addEventListener('click', (e) => {
        if (e.target.classList.contains('conv-delete')) {
          e.stopPropagation();
          this._deleteSession(id);
        } else {
          this.switchSession(id);
        }
      });
      this.el.convList.appendChild(item);
    });
  },

  /** ── 恢复上次活跃会话 ── */
  _restoreActiveSession() {
    // 优先恢复上次活跃的
    const lastActive = localStorage.getItem('rag_qa_active_session');
    if (lastActive && this.sessions[lastActive]) {
      this.switchSession(lastActive, false);
    } else if (Object.keys(this.sessions).length > 0) {
      const first = Object.keys(this.sessions).sort(
        (a, b) => (this.sessions[b].createdAt || 0) - (this.sessions[a].createdAt || 0)
      )[0];
      this.switchSession(first, false);
    } else {
      this._showEmptyState();
    }
  },

  /** ── 事件绑定 ── */
  _bindEvents() {
    // 新建对话
    document.getElementById('btn-new-chat').addEventListener('click', () => this.newSession());
    // 发送
    this.el.sendBtn.addEventListener('click', () => this._send());
    // Enter 发送、Shift+Enter 换行
    this.el.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this._send();
      }
    });
    // 自动 resize
    this.el.chatInput.addEventListener('input', () => {
      this.el.chatInput.style.height = 'auto';
      this.el.chatInput.style.height = Math.min(this.el.chatInput.scrollHeight, 120) + 'px';
    });
  },

  /** ── 新建会话 ── */
  newSession() {
    const id = Utils.uuid();
    this.sessions[id] = {
      id,
      title: '新对话',
      createdAt: new Date().toISOString(),
      messages: [],
    };
    this._saveSessions();
    this.switchSession(id);
  },

  /** ── 切换会话 ── */
  switchSession(id, saveActive = true) {
    this.activeSession = id;
    if (saveActive) localStorage.setItem('rag_qa_active_session', id);
    this._renderConvList();
    this._renderMessages();
    this.el.chatInput.focus();
  },

  /** ── 删除会话 ── */
  _deleteSession(id) {
    if (!confirm('确定删除这个对话？')) return;
    API.clearSession(id).catch(() => {});
    delete this.sessions[id];
    this._saveSessions();
    if (this.activeSession === id) {
      const remaining = Object.keys(this.sessions);
      if (remaining.length > 0) {
        this.switchSession(remaining[0]);
      } else {
        this.activeSession = 'default';
        localStorage.removeItem('rag_qa_active_session');
        this._showEmptyState();
      }
    }
    this._renderConvList();
  },

  /** ── 渲染当前会话的消息 ── */
  _renderMessages() {
    this.el.chatMessages.innerHTML = '';
    const session = this.sessions[this.activeSession];
    if (!session || session.messages.length === 0) {
      this._showEmptyState();
      return;
    }
    session.messages.forEach((msg, i) => {
      if (msg.role === 'user') {
        this._addUserBubble(msg.content);
      } else {
        const { div, bubble } = this._addAssistantBubble();
        bubble.innerHTML = Markdown.render(msg.content);
        if (msg.sources && msg.sources.length > 0) {
          div.appendChild(this._buildSourcesEl(msg.sources));
        }
      }
    });
    this._scrollBottom();
  },

  /** ── 显示空状态 ── */
  _showEmptyState() {
    this.el.chatMessages.innerHTML = `
      <div class="chat-empty">
        <div class="chat-empty-icon">🔍</div>
        <h2>RAG 企业知识库智能问答</h2>
        <p>基于 54 篇 IBM watsonx 技术文档，支持中英文口语提问。
        选择左侧预设问题或直接输入你的问题。</p>
      </div>
    `;
  },

  /** ── 添加用户气泡 ── */
  _addUserBubble(text) {
    const div = document.createElement('div');
    div.className = 'msg user';
    div.innerHTML = `<div class="bubble">${Utils.escapeHtml(text)}</div>`;
    this.el.chatMessages.appendChild(div);
    this._scrollBottom();
  },

  /** ── 添加 Assistant 气泡（含 typing cursor） ── */
  _addAssistantBubble() {
    const div = document.createElement('div');
    div.className = 'msg assistant';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    const cursor = document.createElement('span');
    cursor.className = 'typing-cursor';
    bubble.appendChild(cursor);
    div.appendChild(bubble);
    this.el.chatMessages.appendChild(div);
    this._scrollBottom();
    return { div, bubble, cursor };
  },

  /** ── 构建来源引用卡片 ── */
  _buildSourcesEl(sources) {
    const section = document.createElement('div');
    section.className = 'sources-section';
    section.innerHTML = '<div class="sources-label">📎 引用来源</div>';

    const grid = document.createElement('div');
    grid.className = 'sources-grid';

    sources.forEach(s => {
      const pct = Utils.pct(s.score || 0);
      const card = document.createElement('div');
      card.className = 'src-card';
      card.title = (s.excerpt || '').slice(0, 300);
      const docName = s.documentName || 'Unknown';
      const downloadUrl = `${API.BASE}/api/documents/download/${encodeURIComponent(docName)}`;
      card.innerHTML = `
        <div class="src-name">${Utils.escapeHtml(docName.replace('.md','').replace(/_/g,' ').slice(0, 50))}</div>
        <div class="src-meta">
          <span>${Utils.escapeHtml(Utils.truncate(s.heading || '', 30) || '(no heading)')}</span>
          <b style="color:var(--accent)">${pct}%</b>
        </div>
        <div class="score-bar"><div class="score-bar-inner" style="width:${pct}%"></div></div>
        <div class="src-excerpt">${Utils.escapeHtml((s.excerpt || '').slice(0, 180))}</div>
        <a class="src-download" href="${downloadUrl}" title="下载源文档 ${Utils.escapeHtml(docName)}" download>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载原文
        </a>
      `;
      grid.appendChild(card);
    });

    section.appendChild(grid);
    return section;
  },

  /** ── 滚动到底部 ── */
  _scrollBottom() {
    requestAnimationFrame(() => {
      this.el.chatMessages.scrollTop = this.el.chatMessages.scrollHeight;
    });
  },

  /** ── 发送消息 ── */
  async _send() {
    const text = this.el.chatInput.value.trim();
    if (!text || this.streaming) return;

    this.streaming = true;
    this.el.sendBtn.disabled = true;
    this.el.chatInput.value = '';
    this.el.chatInput.style.height = 'auto';

    // 确保当前会话存在
    if (this.activeSession === 'default') {
      this.newSession();
    }
    const session = this.sessions[this.activeSession];
    if (!session) { this.streaming = false; return; }

    // 首条消息作为标题
    if (session.messages.length === 0) {
      session.title = text.slice(0, 30) + (text.length > 30 ? '…' : '');
    }

    // 保存用户消息
    session.messages.push({ role: 'user', content: text, timestamp: new Date().toISOString() });
    this._saveSessions();
    this._renderConvList();

    // 移除空状态
    if (this.el.chatMessages.querySelector('.chat-empty')) {
      this.el.chatMessages.innerHTML = '';
    }

    // 显示用户消息
    this._addUserBubble(text);

    // 创建 Assistant 气泡
    const { div, bubble, cursor } = this._addAssistantBubble();
    let accumulator = '';
    let sources = [];

    try {
      const reader = await API.sendMessage(text, this.activeSession);
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split('\n');
          let eventType = '', data = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) data = line.slice(6);
          }

          if (eventType === 'token' && data) {
            accumulator += data;
            bubble.innerHTML = Markdown.render(accumulator);
            bubble.appendChild(cursor);
            this._scrollBottom();
          } else if (eventType === 'sources') {
            try { sources = JSON.parse(data); } catch {}
          }
        }
      }
    } catch (err) {
      bubble.innerHTML = Markdown.render(
        accumulator || `> ❌ 请求失败：${Utils.escapeHtml(err.message)}`
      );
    }

    // 移除 typing cursor
    cursor.remove();
    bubble.innerHTML = Markdown.render(accumulator);

    // 添加来源引用
    if (sources.length > 0) {
      div.appendChild(this._buildSourcesEl(sources));
    }

    // 保存 Assistant 消息
    session.messages.push({
      role: 'assistant',
      content: accumulator,
      sources,
      timestamp: new Date().toISOString(),
    });
    this._saveSessions();

    this.streaming = false;
    this.el.sendBtn.disabled = false;
    this.el.chatInput.focus();
    this._scrollBottom();
  },
};
