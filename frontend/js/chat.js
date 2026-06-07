const Chat = {
  activeSession: "default",
  sessions: {},
  streaming: false,
  el: {},
  _storageKey: "rag_qa_conversations",

  PRESETS: [
    { q: "What foundation models are available in watsonx.ai?", tag: "MODELS" },
    { q: "What tuning parameters are available for IBM foundation models?", tag: "TUNING" },
    { q: "What are tokens and tokenization?", tag: "BASICS" },
    { q: "What is the workflow for a Federated Learning experiment?", tag: "FEDLEARN" },
    { q: "What is the retrieval-augmented generation pattern?", tag: "RAG" },
    { q: "How do I delete a deployment using the Python client?", tag: "DEPLOY" },
    { q: "有哪些基础模型可以使用？", tag: "CN→EN" },
    { q: "联邦学习是怎么回事？", tag: "CN→EN" },
  ],

  init() {
    this.el = {
      convList: document.getElementById("conv-list"),
      presetList: document.getElementById("preset-list"),
      chatMessages: document.getElementById("chat-messages"),
      chatInput: document.getElementById("chat-input"),
      sendBtn: document.getElementById("send-btn"),
      evidenceList: document.getElementById("evidence-list"),
      evidenceCount: document.getElementById("evidence-count"),
      pipelineStatus: document.getElementById("pipeline-status"),
    };
    this._loadSessions();
    this._renderPresets();
    this._renderConvList();
    this._restoreActiveSession();
    this._bindEvents();
    this._setPipelineState("ready");
    Markdown.init();
  },

  _loadSessions() {
    try {
      this.sessions = JSON.parse(localStorage.getItem(this._storageKey) || "{}");
    } catch {
      this.sessions = {};
    }
  },

  _saveSessions() {
    const ids = Object.keys(this.sessions);
    if (ids.length > 30) {
      ids.sort((a, b) => (this.sessions[b].createdAt || "").localeCompare(this.sessions[a].createdAt || ""));
      ids.slice(30).forEach(id => delete this.sessions[id]);
    }
    localStorage.setItem(this._storageKey, JSON.stringify(this.sessions));
  },

  _renderPresets() {
    this.el.presetList.innerHTML = "";
    this.PRESETS.forEach(item => {
      const button = document.createElement("button");
      button.className = "preset-chip";
      button.innerHTML = `<span class="preset-tag">${item.tag}</span>${Utils.escapeHtml(item.q)}`;
      button.addEventListener("click", () => {
        this.el.chatInput.value = item.q;
        this._send();
      });
      this.el.presetList.appendChild(button);
    });
  },

  _renderConvList() {
    this.el.convList.innerHTML = "";
    Object.keys(this.sessions)
      .sort((a, b) => (this.sessions[b].createdAt || "").localeCompare(this.sessions[a].createdAt || ""))
      .forEach(id => {
        const session = this.sessions[id];
        const button = document.createElement("button");
        button.className = `conv-item${id === this.activeSession ? " active" : ""}`;
        button.innerHTML = `<span class="conv-title">${Utils.escapeHtml(session.title || "新对话")}</span><span class="conv-delete" data-id="${id}" title="删除">×</span>`;
        button.addEventListener("click", event => {
          if (event.target.classList.contains("conv-delete")) {
            event.stopPropagation();
            this._deleteSession(id);
            return;
          }
          this.switchSession(id);
        });
        this.el.convList.appendChild(button);
      });
  },

  _restoreActiveSession() {
    const last = localStorage.getItem("rag_qa_active_session");
    if (last && this.sessions[last]) {
      this.switchSession(last, false);
      return;
    }
    const newest = Object.keys(this.sessions).sort(
      (a, b) => (this.sessions[b].createdAt || "").localeCompare(this.sessions[a].createdAt || "")
    )[0];
    if (newest) this.switchSession(newest, false);
    else this._showEmptyState();
  },

  _bindEvents() {
    document.getElementById("btn-new-chat").addEventListener("click", () => this.newSession());
    this.el.sendBtn.addEventListener("click", () => this._send());
    this.el.chatInput.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        this._send();
      }
    });
    this.el.chatInput.addEventListener("input", () => {
      this.el.chatInput.style.height = "auto";
      this.el.chatInput.style.height = `${Math.min(this.el.chatInput.scrollHeight, 120)}px`;
    });
  },

  newSession() {
    const id = Utils.uuid();
    this.sessions[id] = { id, title: "新对话", createdAt: new Date().toISOString(), messages: [] };
    this._saveSessions();
    this.switchSession(id);
  },

  switchSession(id, saveActive = true) {
    this.activeSession = id;
    if (saveActive) localStorage.setItem("rag_qa_active_session", id);
    this._renderConvList();
    this._renderMessages();
    this.el.chatInput.focus();
  },

  _deleteSession(id) {
    if (!confirm("确定删除这个对话？")) return;
    API.clearSession(id).catch(() => {});
    delete this.sessions[id];
    this._saveSessions();
    const remaining = Object.keys(this.sessions);
    if (this.activeSession === id) {
      this.activeSession = remaining[0] || "default";
      if (remaining[0]) this.switchSession(remaining[0]);
      else this._showEmptyState();
    }
    this._renderConvList();
  },

  _renderMessages() {
    this.el.chatMessages.innerHTML = "";
    const session = this.sessions[this.activeSession];
    if (!session || !session.messages.length) {
      this._showEmptyState();
      this._renderEvidencePanel([]);
      return;
    }
    session.messages.forEach(message => {
      if (message.role === "user") {
        this._addUserBubble(message.content);
      } else {
        const { div, bubble } = this._addAssistantBubble(false);
        bubble.innerHTML = Markdown.render(message.content);
        if (message.sources?.length) {
          div.appendChild(this._buildSourcesEl(message.sources));
          this._renderEvidencePanel(message.sources);
        }
      }
    });
    this._scrollBottom();
  },

  _showEmptyState() {
    this.el.chatMessages.innerHTML = `
      <div class="chat-empty">
        <div class="hero-index">01 / TRUSTWORTHY ANSWERS</div>
        <h1>Ask the knowledge base.<br><em>Inspect every answer.</em></h1>
        <p>对 54 篇 IBM watsonx 技术文档执行混合检索、重排序与自适应过滤。每条回答都附带可核验的来源证据。</p>
        <div class="hero-capabilities"><span>HYBRID RETRIEVAL</span><span>BGE RERANK</span><span>STREAMING SSE</span></div>
      </div>`;
  },

  _addUserBubble(text) {
    const div = document.createElement("div");
    div.className = "msg user";
    div.innerHTML = `<div class="bubble">${Utils.escapeHtml(text)}</div>`;
    this.el.chatMessages.appendChild(div);
    this._scrollBottom();
  },

  _addAssistantBubble(withCursor = true) {
    const div = document.createElement("div");
    div.className = "msg assistant";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    let cursor = null;
    if (withCursor) {
      cursor = document.createElement("span");
      cursor.className = "typing-cursor";
      bubble.appendChild(cursor);
    }
    div.appendChild(bubble);
    this.el.chatMessages.appendChild(div);
    this._scrollBottom();
    return { div, bubble, cursor };
  },

  _buildSourcesEl(sources) {
    const section = document.createElement("div");
    section.className = "sources-section";
    section.innerHTML = '<div class="sources-label">CITED EVIDENCE</div>';
    const grid = document.createElement("div");
    grid.className = "sources-grid";
    sources.forEach(source => {
      const score = Utils.pct(source.score || 0);
      const name = source.documentName || "Unknown";
      const card = document.createElement("div");
      card.className = "src-card";
      card.innerHTML = `
        <div class="src-name">${Utils.escapeHtml(name.replace(".md", "").replace(/_/g, " "))}</div>
        <div class="src-meta"><span>${Utils.escapeHtml(Utils.truncate(source.heading || "Unsectioned", 34))}</span><b>${score}%</b></div>
        <div class="score-bar"><div class="score-bar-inner" style="width:${score}%"></div></div>
        <div class="src-excerpt">${Utils.escapeHtml((source.excerpt || "").slice(0, 160))}</div>
        <a class="src-download" href="${API.BASE}/api/documents/download/${encodeURIComponent(name)}" download>下载原文 ↗</a>`;
      grid.appendChild(card);
    });
    section.appendChild(grid);
    return section;
  },

  _setPipelineState(state) {
    const stages = [...document.querySelectorAll("#pipeline-trace li[data-stage]")];
    const stageOrder = ["rewrite", "retrieve", "fusion", "rerank", "filter", "generate"];
    const activeIndex = state === "ready" ? -1 : stageOrder.indexOf(state);
    stages.forEach((node, index) => {
      node.classList.toggle("complete", state === "complete" || (activeIndex >= 0 && index < activeIndex));
      node.classList.toggle("active", activeIndex === index);
    });
    if (this.el.pipelineStatus) {
      this.el.pipelineStatus.textContent =
        state === "ready" ? "READY" : state === "complete" ? "COMPLETE" : "RUNNING";
    }
  },

  _renderEvidencePanel(sources) {
    if (!this.el.evidenceList) return;
    this.el.evidenceCount.textContent = `${sources.length} SOURCE${sources.length === 1 ? "" : "S"}`;
    if (!sources.length) {
      this.el.evidenceList.innerHTML = '<div class="evidence-empty">运行一次查询后，这里会显示当前回答使用的文档、章节与相关度。</div>';
      return;
    }
    this.el.evidenceList.innerHTML = sources.slice(0, 5).map(source => {
      const score = Utils.pct(source.score || 0);
      const name = (source.documentName || "Unknown").replace(".md", "").replace(/_/g, " ");
      return `<article class="evidence-item">
        <div class="evidence-item-head"><strong title="${Utils.escapeHtml(name)}">${Utils.escapeHtml(name)}</strong><b>${score}%</b></div>
        <p>${Utils.escapeHtml(Utils.truncate(source.heading || "Unsectioned", 46))}</p>
        <i style="--score:${score}%"></i>
      </article>`;
    }).join("");
  },

  _scrollBottom() {
    requestAnimationFrame(() => {
      this.el.chatMessages.scrollTop = this.el.chatMessages.scrollHeight;
    });
  },

  async _send() {
    const text = this.el.chatInput.value.trim();
    if (!text || this.streaming) return;
    this.streaming = true;
    this.el.sendBtn.disabled = true;
    this.el.chatInput.value = "";
    this.el.chatInput.style.height = "auto";

    if (this.activeSession === "default") this.newSession();
    const session = this.sessions[this.activeSession];
    if (!session) return;
    if (!session.messages.length) session.title = `${text.slice(0, 30)}${text.length > 30 ? "…" : ""}`;
    session.messages.push({ role: "user", content: text, timestamp: new Date().toISOString() });
    this._saveSessions();
    this._renderConvList();

    if (this.el.chatMessages.querySelector(".chat-empty")) this.el.chatMessages.innerHTML = "";
    this._addUserBubble(text);
    this._renderEvidencePanel([]);
    this._setPipelineState("rewrite");
    const { div, bubble, cursor } = this._addAssistantBubble();
    let accumulator = "";
    let sources = [];

    try {
      const reader = await API.sendMessage(text, this.activeSession);
      this._setPipelineState("retrieve");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          if (!part.trim()) continue;
          let eventType = "";
          let data = "";
          part.split("\n").forEach(line => {
            if (line.startsWith("event: ")) eventType = line.slice(7).trim();
            if (line.startsWith("data: ")) data = line.slice(6);
          });
          if (eventType === "token" && data) {
            this._setPipelineState("generate");
            accumulator += data;
            bubble.innerHTML = Markdown.render(accumulator);
            bubble.appendChild(cursor);
            this._scrollBottom();
          } else if (eventType === "sources") {
            try {
              sources = JSON.parse(data);
              this._renderEvidencePanel(sources);
            } catch {}
          }
        }
      }
    } catch (error) {
      accumulator = accumulator || `> 请求失败：${Utils.escapeHtml(error.message)}`;
    }

    cursor?.remove();
    bubble.innerHTML = Markdown.render(accumulator);
    if (sources.length) div.appendChild(this._buildSourcesEl(sources));
    session.messages.push({ role: "assistant", content: accumulator, sources, timestamp: new Date().toISOString() });
    this._saveSessions();
    this._setPipelineState("complete");
    this.streaming = false;
    this.el.sendBtn.disabled = false;
    this.el.chatInput.focus();
    this._scrollBottom();
  },
};
