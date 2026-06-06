/* ═══════════════════════════════════════════
   Documents — 文档管理面板
   依赖: Utils, API
   ═══════════════════════════════════════════ */

const Documents = {
  /** DOM 引用 */
  el: {},

  /** 文档数据缓存 */
  _docs: [],

  /** ── 初始化 ── */
  init() {
    this.el = {
      statTotal: document.getElementById('doc-stat-total'),
      statIngested: document.getElementById('doc-stat-ingested'),
      statChunks: document.getElementById('doc-stat-chunks'),
      statLast: document.getElementById('doc-stat-last'),
      tableBody: document.getElementById('doc-table-body'),
      tableWrap: document.getElementById('doc-table-wrap'),
      btnReingest: document.getElementById('btn-reingest'),
      btnUpload: document.getElementById('btn-upload'),
      modalOverlay: document.getElementById('ingest-modal'),
      modalCancel: document.getElementById('ingest-modal-cancel'),
      modalConfirm: document.getElementById('ingest-modal-confirm'),
      ingestPath: document.getElementById('ingest-path'),
      ingestCategory: document.getElementById('ingest-category'),
      ingestForce: document.getElementById('ingest-force'),
    };

    this._bindEvents();
  },

  /** ── 事件绑定 ── */
  _bindEvents() {
    this.el.btnReingest.addEventListener('click', () => this._handleReingest());
    this.el.btnUpload.addEventListener('click', () => this._openModal());
    this.el.modalCancel.addEventListener('click', () => this._closeModal());
    this.el.modalOverlay.addEventListener('click', (e) => {
      if (e.target === this.el.modalOverlay) this._closeModal();
    });
    this.el.modalConfirm.addEventListener('click', () => this._handleIngest());
  },

  /** ── 加载数据 ── */
  async load() {
    try {
      const [docsRes, statusRes] = await Promise.all([
        API.listDocuments(),
        API.ingestionStatus(),
      ]);
      this._docs = docsRes.documents || [];
      this._renderStats(docsRes, statusRes);
      this._renderTable();
    } catch (err) {
      console.error('[Documents] 加载失败:', err);
      Toast.show('加载文档列表失败：' + err.message, 'error');
      this._showTableError(err.message);
    }
  },

  /** ── 渲染统计卡片 ── */
  _renderStats(docsRes, statusRes) {
    this.el.statTotal.textContent = docsRes.count || 0;
    this.el.statIngested.textContent = docsRes.ingested || 0;
    this.el.statChunks.textContent = statusRes.total_chunks || 0;
    this.el.statLast.textContent = Utils.formatDate(statusRes.last_ingestion);
  },

  /** ── 渲染文档表格 ── */
  _renderTable() {
    if (this._docs.length === 0) {
      this.el.tableBody.innerHTML = `
        <tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-dim);">
          暂无文档
        </td></tr>`;
      return;
    }

    this.el.tableBody.innerHTML = this._docs.map(doc => `
      <tr>
        <td class="doc-name-cell" title="${Utils.escapeHtml(doc.name)}">${Utils.escapeHtml(doc.name)}</td>
        <td>${doc.category ? `<span class="badge cat">${Utils.escapeHtml(doc.category)}</span>` : '—'}</td>
        <td>${doc.ingested ? doc.chunks : '—'}</td>
        <td>${doc.ingested
          ? '<span class="badge ok">已摄入</span>'
          : '<span class="badge no">未摄入</span>'}</td>
        <td>${Utils.formatDate(doc.ingested_at)}</td>
        <td class="action-cell">
          ${doc.ingested
            ? `<button class="btn btn-sm danger" data-delete="${Utils.escapeHtml(doc.name)}">删除索引</button>`
            : `<button class="btn btn-sm" data-ingest="${Utils.escapeHtml(doc.name)}">摄入</button>`
          }
        </td>
      </tr>
    `).join('');

    // 绑定操作按钮
    this.el.tableBody.querySelectorAll('[data-delete]').forEach(btn => {
      btn.addEventListener('click', () => this._handleDelete(btn.dataset.delete));
    });
    this.el.tableBody.querySelectorAll('[data-ingest]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.el.ingestPath.value = this._docPath(btn.dataset.ingest);
        this._openModal();
      });
    });
  },

  /** ── 文档完整路径 ── */
  _docPath(fileName) {
    // 推断路径：项目根 data/documents/ 下
    return `D:\\大学作业文件夹\\自制软件\\rag-enterprise-qa\\data\\documents\\${fileName}`;
  },

  /** ── 显示表格错误 ── */
  _showTableError(msg) {
    this.el.tableBody.innerHTML = `
      <tr><td colspan="6" style="text-align:center;padding:40px;color:var(--red);">
        ⚠ 加载失败：${Utils.escapeHtml(msg)}
      </td></tr>`;
  },

  /** ── Modal 操作 ── */
  _openModal() {
    this.el.modalOverlay.classList.add('open');
    this.el.ingestPath.focus();
  },
  _closeModal() {
    this.el.modalOverlay.classList.remove('open');
    this.el.ingestPath.value = '';
    this.el.ingestForce.checked = false;
  },

  /** ── 摄入文档 ── */
  async _handleIngest() {
    const filePath = this.el.ingestPath.value.trim();
    if (!filePath) {
      Toast.show('请输入文件路径', 'error');
      return;
    }

    this.el.modalConfirm.disabled = true;
    this.el.modalConfirm.textContent = '摄入中...';

    try {
      const result = await API.ingestDocument(
        filePath,
        this.el.ingestCategory.value || 'General',
        this.el.ingestForce.checked
      );
      Toast.show(
        result.status === 'skipped'
          ? `⏭ ${result.file_name} 已存在，跳过`
          : `✓ ${result.file_name} 摄入完成，${result.chunks} 个 chunk`,
        'success'
      );
      this._closeModal();
      await this.load();
    } catch (err) {
      Toast.show('摄入失败：' + err.message, 'error');
    } finally {
      this.el.modalConfirm.disabled = false;
      this.el.modalConfirm.textContent = '确认摄入';
    }
  },

  /** ── 删除文档索引 ── */
  async _handleDelete(fileName) {
    if (!confirm(`确定从索引中删除 "${fileName}"？\n（不会删除原始文件）`)) return;

    try {
      await API.deleteDocument(fileName);
      Toast.show(`已从索引中移除 ${fileName}`, 'info');
      await this.load();
    } catch (err) {
      Toast.show('删除失败：' + err.message, 'error');
    }
  },

  /** ── 全量重摄入 ── */
  async _handleReingest() {
    if (!confirm('⚠ 全量重摄入将会清空当前所有索引并重新处理全部文档。\n\n确定继续？')) return;

    this.el.btnReingest.disabled = true;
    this.el.btnReingest.textContent = '重摄入中...';
    Toast.show('正在全量重摄入，请稍候...', 'info');

    try {
      const result = await API.reingestAll();
      const failed = result.failed || [];
      if (failed.length > 0) {
        const names = failed.map(f => f.file).join(', ');
        Toast.show(`重摄入完成：${result.total_files} 文件，${result.total_chunks} chunks。⚠ 失败：${names}`, 'error');
      } else {
        Toast.show(`✓ 全量重摄入完成：${result.total_files} 文件，${result.total_chunks} chunks`, 'success');
      }
      await this.load();
    } catch (err) {
      Toast.show('重摄入失败：' + err.message, 'error');
    } finally {
      this.el.btnReingest.disabled = false;
      this.el.btnReingest.textContent = '🔄 全量重摄入';
    }
  },
};
