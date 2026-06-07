# Trustworthy AI Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有问答 SPA 改造成三栏可信 AI 控制台，同时保留全部现有业务能力。

**Architecture:** 保留原生 HTML/CSS/JS 架构和现有模块边界。`index.html` 负责新骨架，`style.css` 负责响应式视觉系统，`chat.js` 只增加链路和证据面板的状态同步。

**Tech Stack:** HTML5、CSS3、原生 JavaScript、FastAPI SSE、pytest 静态契约测试

---

### Task 1: 锁定新控制台结构

**Files:**
- Create: `backend/tests/test_frontend_console.py`
- Modify: `frontend/index.html`

- [x] 编写失败测试，要求页面包含 `console-rail`、`evidence-panel`、六个链路节点和三项当前基线。
- [x] 运行 `pytest tests/test_frontend_console.py -q`，确认因结构缺失失败。
- [x] 重构 `index.html`，保留现有 DOM id 和脚本加载顺序。
- [x] 再次运行测试并确认通过。

### Task 2: 实现视觉与响应式布局

**Files:**
- Modify: `frontend/css/style.css`
- Test: `backend/tests/test_frontend_console.py`

- [x] 增加失败测试，要求桌面三栏和 1080px、760px 两级响应式规则。
- [x] 运行目标测试并确认失败。
- [x] 实现深色轨道、中央工作区、证据侧栏、英雄区和移动端折叠。
- [x] 运行目标测试并确认通过。

### Task 3: 同步真实链路与证据

**Files:**
- Modify: `frontend/js/chat.js`
- Test: `backend/tests/test_frontend_console.py`

- [x] 增加失败测试，要求 `setPipelineState` 和 `renderEvidencePanel`。
- [x] 运行目标测试并确认失败。
- [x] 在发送、流式生成、sources 到达和结束时更新右侧面板。
- [x] 运行目标测试和现有前端相关测试。

### Task 4: 浏览器验收

**Files:**
- Verify: `frontend/index.html`

- [x] 启动本地服务并打开实际应用。
- [x] 验证 1440px 桌面布局、760px 移动布局、标签切换和控制台日志。
- [x] 运行 `git diff --check` 与前端测试集。
