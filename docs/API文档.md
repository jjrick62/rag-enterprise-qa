# API 文档

> Base URL：`http://localhost:8000`
> 当前实现：FastAPI + SSE

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat/send` | SSE 流式问答 |
| DELETE | `/api/chat/session/{session_id}` | 清除会话 |
| POST | `/api/documents/ingest` | 摄入或更新文档 |
| GET | `/api/documents/list` | 文档及摄入状态 |
| GET | `/api/documents/status` | 摄入统计 |
| DELETE | `/api/documents/{file_name}` | 删除文档索引 |
| POST | `/api/documents/reingest-all` | 安全清空并重建索引 |

## GET /api/health

```json
{"status": "ok"}
```

## POST /api/chat/send

请求：

```json
{
  "question": "What tuning parameters are available?",
  "category": null,
  "session_id": "default"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `question` | string | 是 | 用户问题 |
| `category` | string/null | 否 | 文档分类过滤 |
| `session_id` | string | 否 | 默认 `default`；其他值启用进程内多轮历史 |

响应类型：`text/event-stream`

```text
event: token
data: The available parameters...

event: sources
data: [{"documentName":"...","heading":"...","excerpt":"...","score":0.94}]

event: done
data:
```

`contexts` 是内部评测事件，不会发送给浏览器。

## DELETE /api/chat/session/{session_id}

```json
{"session_id": "demo", "status": "cleared"}
```

## POST /api/documents/ingest

```json
{
  "file_path": "../data/documents/Box_connection.md",
  "category": "IBM_Docs",
  "force": false
}
```

响应：

```json
{
  "file_name": "Box_connection.md",
  "chunks": 8,
  "status": "ok"
}
```

`status` 可能是 `ok`、`skipped` 或 `updated`。文件不存在返回 404；强制更新时旧索引删除失败返回 500。

## GET /api/documents/list

```json
{
  "count": 54,
  "ingested": 54,
  "documents": [
    {
      "name": "Box_connection.md",
      "ingested": true,
      "chunks": 8,
      "category": "IBM_Docs",
      "ingested_at": "2026-06-06T12:00:00"
    }
  ]
}
```

## GET /api/documents/status

```json
{
  "total_ingested": 54,
  "total_chunks": 637,
  "last_ingestion": "2026-06-06T12:00:00"
}
```

## DELETE /api/documents/{file_name}

只删除 ChromaDB 和 BM25 索引，不删除原始 Markdown。

```json
{
  "file_name": "Box_connection.md",
  "deleted_vectors": 8,
  "status": "ok"
}
```

## POST /api/documents/reingest-all

通过 Retriever `clear()` 清空 ChromaDB collection 和内存 BM25，再摄入 `data/documents/*.md`。

```json
{
  "total_chunks": 637,
  "total_files": 54,
  "failed": [],
  "status": "ok"
}
```

## 限制

- 会话历史仅保存在当前进程内。
- CORS 当前为开发配置。
- 文档管理路由通过应用内部 Pipeline 执行，属于 MVP 管理接口。
