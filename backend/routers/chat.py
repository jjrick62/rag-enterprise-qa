"""对话路由——SSE 流式问答端点

POST /api/chat/send  →  SSE 流返回
  event: token    逐 token 文本
  event: sources  引用来源列表（JSON）
  event: done     流结束
"""
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from schemas.chat import QueryRequest
from services.pipeline import RAGPipeline

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_pipeline() -> RAGPipeline:
    """懒加载获取全局 Pipeline——避免模块导入时的循环依赖"""
    from main import app  # noqa: E402
    return app.state.pipeline


async def _sse_generator(question: str, category: str | None, pipeline: RAGPipeline):
    """将 RAGPipeline.query() 的 GenerateEvent 转为 SSE 文本格式"""
    async for event in pipeline.query(question, category_filter=category):
        if event.type == "token":
            # token 可能包含换行符，直接拼接没问题
            yield f"event: token\ndata: {event.content}\n\n"
        elif event.type == "sources":
            sources_json = json.dumps(
                [{"documentName": s.document_name,
                  "heading": s.heading,
                  "excerpt": s.excerpt,
                  "score": s.score} for s in (event.sources or [])],
                ensure_ascii=False,
            )
            yield f"event: sources\ndata: {sources_json}\n\n"
        elif event.type == "done":
            yield "event: done\ndata: \n\n"


@router.post("/send")
async def send_message(request: QueryRequest):
    """发送消息，返回 SSE 流"""
    pipeline = _get_pipeline()
    return StreamingResponse(
        _sse_generator(request.question, request.category, pipeline),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )
