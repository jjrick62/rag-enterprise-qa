# RAG 企业制度智能问答

## 项目概述
基于 RAG（检索增强生成）的企业管理制度智能问答系统。用户上传企业文档（员工手册、IT规范、报销制度等），通过自然语言提问，系统从文档中检索相关内容并生成带引用溯源的答案。

## 技术栈
- **后端**: Python + FastAPI + LangChain
- **前端**: React + TypeScript
- **向量数据库**: ChromaDB
- **Embedding**: BAAI/bge-small-zh-v1.5（本地）
- **LLM**: DeepSeek API（云端）
- **文档解析**: PyPDF2 + python-docx + markdown

## 项目结构
```
rag-enterprise-qa/
├── backend/           # Python FastAPI 后端
├── frontend/          # React 前端
├── data/
│   ├── documents/     # 原始文档
│   └── chroma_db/     # 向量数据库持久化
└── claude_memory/     # 项目记忆
```

## 核心功能
1. 多文档上传与解析（PDF/DOCX/Markdown）
2. 智能分块 + 本地 Embedding
3. 分类检索（按文档类别过滤）
4. 引用溯源（答案关联到原文段落）
5. 对话式问答界面

## 当前状态
🟡 设计阶段 — 方案二已确认，正在细化技术方案
