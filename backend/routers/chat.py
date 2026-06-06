"""对话路由——SSE 流式问答端点 + 多轮对话

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
from services.conversation import ConversationManager

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 全局会话管理器（进程内，重启丢失——demo 够用）
conv_manager = ConversationManager()


def _get_pipeline() -> RAGPipeline:
    """懒加载获取全局 Pipeline"""
    from main import app  # noqa: E402
    return app.state.pipeline


def _build_question_with_history(raw_question: str, session_id: str) -> str:
    """把对话历史注入问题——让 LLM 知道上下文"""
    if session_id == "default":
        return raw_question  # 无历史，直接返回原问题

    history_block = conv_manager.build_history_block(session_id)
    if not history_block:
        return raw_question

    return history_block + f"【当前问题】\n{raw_question}"


async def _sse_generator(
    question: str, category: str | None, pipeline: RAGPipeline,
    session_id: str, generation_context: str | None = None,
):
    """Generate SSE events and accumulate full answer for session saving"""
    full_answer = ""
    async for event in pipeline.query(
        question, category_filter=category,
        generation_context=generation_context,
    ):
        if event.type == "token":
            full_answer += event.content
            yield f"event: token\ndata: {event.content}\n\n"
        elif event.type == "contexts":
            # 内部评测数据，不向浏览器发送完整检索文本。
            continue
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

    # 保存本轮对话
    if session_id != "default":
        conv_manager.add_turn(session_id, question, full_answer)


@router.post("/send")
async def send_message(request: QueryRequest):
    """发送消息，返回 SSE 流。支持多轮对话（session_id）"""
    pipeline = _get_pipeline()
    # 历史只注入生成阶段，不影响检索
    gen_context = _build_question_with_history(
        request.question, request.session_id
    )
    return StreamingResponse(
        _sse_generator(
            request.question, request.category, pipeline,
            request.session_id, gen_context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """清除指定会话"""
    conv_manager.delete_session(session_id)
    return {"session_id": session_id, "status": "cleared"}
