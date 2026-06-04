# API 文档

> 当前版本：v0.1（MVP）
> Base URL：`http://localhost:8000`

---

## 端点一览

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | ✅ |
| POST | `/api/chat/send` | SSE 流式问答 | ✅ |
| POST | `/api/documents/ingest` | 文档摄入 | ✅ |
| GET | `/api/documents/list` | 文档列表 | ✅ |

---

## GET /api/health

健康检查，用于确认服务是否正常运行。

**响应 200：**
```json
{"status": "ok"}
```

---

## POST /api/chat/send

发送问题，SSE 流式返回回答。

**请求体：**
```json
{
  "question": "How do I deploy a Decision Optimization model?",
  "category": null
}
```
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 用户问题 |
| category | string \| null | 否 | 限定检索的文档类别，null 为全库检索 |

**响应：** `text/event-stream`

```
event: token
data: 根据

event: token
data: 现有文档

event: sources
data: {"sources":[{"documentName":"xxx.md","heading":"...","excerpt":"...","score":0.94}]}

event: done
data: 
```

| 事件类型 | data 内容 | 说明 |
|----------|----------|------|
| `token` | 纯文本字符串 | 回答的单个 token，前端逐字拼接渲染 |
| `sources` | JSON 数组（Source 对象） | 所有引用来源，流结束后一次性发送 |
| `done` | 空 | 流结束信号 |

**Source 对象结构：**
```json
{
  "documentName": "Supported_foundation_models_available_with_watsonx.ai.md",
  "heading": "Supported foundation models",
  "excerpt": "The following models are available in watsonx.ai...",
  "score": 0.9412
}
```

**cURL 示例：**
```bash
curl -N -X POST http://localhost:8000/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"question": "What foundation models are available?"}'
```

---

## POST /api/documents/ingest

摄入单篇文档。文档会被解析→分块→Embedding→入库。

**请求体：**
```json
{
  "file_path": "../data/documents/Supported_foundation_models.md",
  "category": "IBM_Docs"
}
```
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | 是 | 文档文件的相对或绝对路径 |
| category | string | 否 | 文档分类标签，默认 "General" |

**响应 200：**
```json
{
  "file_name": "Supported_foundation_models.md",
  "chunks": 8,
  "status": "ok"
}
```

**响应 404：** 文件不存在
```json
{"detail": "文件不存在: ../data/documents/xxx.md"}
```

---

## GET /api/documents/list

列出 `data/documents/` 目录下所有 `.md` 文件。

**响应 200：**
```json
{
  "count": 54,
  "documents": [
    "Box_connection.md",
    "Building_reusable_prompts.md",
    "Deleting_a_deployment.md",
    "..."
  ]
}
```

---

## 规划中的端点（v0.2+）

| 方法 | 路径 | 说明 |
|------|------|------|
| DELETE | `/api/documents/{id}` | 删除文档及关联向量 |
| POST | `/api/documents/reingest` | 批量重建索引 |
| GET | `/api/eval/hit-rate` | 检索命中率评估 |
| POST | `/api/chat/send` | 增加 `session_id` 支持多轮对话 |
