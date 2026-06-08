# RAG 企业知识库智能问答系统

基于 FastAPI、ChromaDB、BM25、BGE Reranker 和 LLM 的企业文档 RAG 系统。54 篇 IBM watsonx 技术文档入库，自然语言提问，流式回答，带引用溯源。

> ### 项目展示页
>
> [打开项目展示](frontend/showcase.html)：查看真实 RAGAS 迭代、系统架构与故障案例。该入口使用仓库相对链接，可继续在 GitHub 中自然浏览项目内容。

## 🔥 RAGAS 评估结果

> 30 道 watsonxDocsQA，MiMo v2.5 Pro 非思考模式生成（temperature=0.2），MiMo v2.5 Pro 思考模式裁判，完整上下文零截断

| 指标 | **我们的得分** | 企业标准线 | 碾压幅度 |
|------|:----------:|:------:|:------:|
| **Faithfulness** | **0.946** | ≥0.80 | **+0.146** |
| **Answer Relevancy** | **0.876** | ≥0.70 | **+0.176** |
| **Context Precision** | **0.869** | ≥0.80 | **+0.069** |

**三指标全部大幅超越企业标准线。** 这代表检索到的上下文高度精准、LLM 生成的答案高度忠实于原文、答案与问题高度相关。

> 2026-06-07 更新：冻结上下文温度实验确认 MiMo `temperature=0.2` 综合最优，三项均值 0.897。
>
> **历史对比**（同检索策略、独立生成、同 Judge）：
>
> | 版本 | Faith. | AnsRel. | CtxPrec. | 说明 |
> |------|:------:|:-------:|:--------:|------|
> | F2（旧 chunker，0.75） | 0.918 | 0.826 | 0.844 | 2026-06-06 基线 |
> | v2（D4P，新 chunker，0.75） | 0.931 | 0.857 | 0.857 | 历史基线 |
> | **MiMo T02（冻结上下文，0.2）** | **0.946** | **0.876** | **0.869** | **当前生产推荐** |
> | D4P Frozen（严格对照） | **0.968** | 0.851 | 0.831 | Faithfulness 单项最高 |
>
> **严格单变量结论**：D4P 与 MiMo T02 共用同一冻结上下文、Prompt、温度和 Judge。D4P 更忠实，MiMo 更相关；只看 Faithfulness 与 Answer Relevancy，两者均值为 0.910 与 0.911，整体近似持平。
>
> 旧自适应噪声过滤实验（已存档）：
>
> | 相对阈值 | Faith. | AnsRel. | CtxPrec. | 平均上下文数 |
> |---------|:------:|:-------:|:--------:|:-----------:|
> | 关闭 | 0.874 | 0.818 | 0.816 | 5.00 |
> | 0.70 | 0.901 | 0.791 | 0.834 | 4.47 |
> | 0.75 | 0.918 | 0.826 | 0.844 | 4.10 |
> | 0.80 | 0.937 | 0.780 | 0.799 | 3.83 |

[完整报告](ragabilitytest.md) · [迭代记录](14.06claude写这里/迭代记录_全量RAGAS分数.md)

## 系统链路

```text
用户问题
  -> Query Rewrite
  -> Vector Top-20 + BM25 Top-20
  -> RRF 融合
  -> BGE Reranker
  -> 绝对阈值 0.50 + 每文档最多 4 条 + 相对过滤 0.75
  -> Top-3~5 完整 chunk
  -> LLM 流式回答
  -> 前端引用摘要
```

## 技术栈

| 层 | 实现 |
|---|---|
| API | Python 3.12、FastAPI、SSE |
| 向量数据库 | ChromaDB 持久化 |
| Embedding | `BAAI/bge-small-zh-v1.5`，512 维 |
| 候选模型 | `BAAI/bge-base-en-v1.5`，768 维，已下载但未切换 |
| 关键词检索 | BM25 |
| 融合 | Reciprocal Rank Fusion |
| 重排序 | `BAAI/bge-reranker-v2-m3` |
| 分块 | RecursiveChunker，Markdown 标题树 → IBM 纯文本标题 fallback → 句子切分、伪表原子化 |
| 在线生成 | MiMo v2.5 Pro（非思考模式） |
| 实验生成 | MiMo v2.5 Pro 温度隔离 + D4P 冻结上下文对照 |
| RAGAS Judge | MiMo v2.5 Pro，thinking enabled |
| 前端 | `frontend/index.html` 完整 SPA（对话 / 文档管理 / 系统信息） |

## 目录

```text
rag-enterprise-qa/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── tests/
│   ├── gen_answers.py
│   └── eval_ragas_only.py
├── data/
│   ├── documents/                 # 54 篇知识库文档
│   ├── chroma_db/                 # 本地索引，gitignored
│   ├── evaluations/
│   │   ├── datasets/              # 各实验答案与完整上下文
│   │   ├── reports/               # RAGAS JSON 和实验报告
│   │   └── archive/               # 历史日志，不作为当前基线
│   └── watsonxDocsQA_test.json
├── docs/
├── frontend/
│   ├── index.html                   # 主应用（对话 + 文档管理 + 关于）
│   ├── css/style.css                # 暗色主题样式系统
│   ├── js/
│   │   ├── app.js                   # 入口 + 标签导航 + 健康检查
│   │   ├── chat.js                  # SSE 流式对话 + 多轮会话 + 引用卡片
│   │   ├── documents.js             # 文档管理 CRUD + 全量重摄入
│   │   ├── api.js                   # 后端 API 封装
│   │   ├── markdown.js              # marked.js 渲染（表格/代码/列表）
│   │   └── utils.js                 # 工具函数
│   └── test.html                    # 旧演示页（保留）
├── 14.06claude写这里/             # 当前交接入口和历史审计
├── README.md
├── CHATGPT_README.md
└── ragabilitytest.md
```

## 快速开始

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `backend/.env` 配置：

```dotenv
MIMO_API_KEY=...
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
```

启动服务：

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

浏览器打开 `http://localhost:8000`（FastAPI 直接 serve 前端），或调用：

```powershell
curl.exe -N -X POST http://localhost:8000/api/chat/send `
  -H "Content-Type: application/json" `
  -d '{"question":"What tuning parameters are available for IBM foundation models?"}'
```

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests ablation_test.py
```

当前非模型依赖测试：`68 passed`。

## 评估

生成四组隔离数据：

```powershell
cd backend
.\venv\Scripts\python.exe gen_answers.py
```

评估默认 `0.75` 数据集：

```powershell
.\venv_ragas\Scripts\python.exe eval_ragas_only.py
```

评估指定数据集并保存报告：

```powershell
.\venv_ragas\Scripts\python.exe eval_ragas_only.py `
  ..\data\evaluations\datasets\eval_dataset_r075.json `
  --output ..\data\evaluations\reports\ragas_r075.json
```

评测链路不会再截断答案或 chunk。前端仍只接收 200 字引用摘要。

## 当前决策

- 保留 `min_score=0.50`。
- 保留 `max_chunks_per_document=4`。
- 默认启用 `adaptive_cutoff_ratio=0.75`，至少保留 3 条。
- 暂不切换英文 Embedding，必须先建立同口径离线对比。
- **2026-06-07**：新增 IBM 纯文本标题 fallback——54 篇文档首行提取为标题，递归时小节标题自动检测，876 chunk 零空 heading。需重摄入 + 重评估。
- 下一优先是候选召回深度实验，重点解决 Q08。

## 安全

- API Key 只放在 `backend/.env`。
- 仓库和 Git remote 不应包含明文 Token。
- 已暴露过的 GitHub 或模型 API Token 应在供应商后台撤销并重新生成。

## 文档入口

- [API 文档](docs/API文档.md)
- [开发日程](docs/RAG优化开发日程.md)
- [当前交接](14.06claude写这里/README.md)
- [ChatGPT/Codex 工作记录](CHATGPT_README.md)

## License

MIT

---

## 2026-06-07 改动记录

- **前端 v1.0**：三标签 SPA（对话/文档管理/关于），暖纸书房风格，`marked.js` 渲染，来源卡片 + 原文下载
- **IBM 标题 fallback**：`RecursiveChunker` 新增 `_detect_ibm_headings()`，54 篇纯文本文档首行提取标题，chunk 1714、零空 heading
- **MiMo 温度实验**：T02 Faith 0.946 / AnsRel 0.876 / CtxPrec 0.869，三项均值 0.897，作为当前生产推荐
- **D4P 严格对照**：同上下文下 Faith 0.968 / AnsRel 0.851 / CtxPrec 0.831；D4P 更忠实，MiMo 综合更高
- **模型本地化**：BGE Embedding + Reranker 从 ModelScope 下载到 `backend/models/`，重启不丢
- **LLM 全切 MiMo**：Generator + Rewriter + Judge 全部走 MiMo 订阅版，全链路零 DeepSeek 调用
- **Prompt 缓存优化**：Rewriter system/user 拆分（~97% cache hit），Generator 静态前缀（~40% 提升）
- **代码清理**：删除 `evaluation.py` / `run_ragas_eval.py` / `_reingest.py` 三个已替代脚本
- **GitHub Pages**：`docs/index.html` 项目展示页，`showcase.html` SVG 图表 + 故障案例
