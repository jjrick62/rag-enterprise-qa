"""文档管理路由——摄入/列表/删除/状态"""
import os
import json
import glob
import hashlib
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/documents", tags=["documents"])

# 摄入状态记录
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ingestion_state.json")


class IngestRequest(BaseModel):
    file_path: str
    category: str = "General"
    force: bool = False  # 强制重新摄入（覆盖已存在的）


class IngestResponse(BaseModel):
    file_name: str
    chunks: int
    status: str  # "ok" | "skipped" | "updated"


def _get_pipeline():
    from main import app
    return app.state.pipeline


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}}


def _save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _file_hash(file_path: str) -> str:
    """计算文件 MD5，用于去重检测"""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(req: IngestRequest):
    """摄入单篇文档——解析→分块→Embedding→入库

    - 自动去重：相同文件已摄入则跳过
    - force=True：强制重新摄入（先删旧的再摄入新的）
    """
    if not os.path.isfile(req.file_path):
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在: {req.file_path}",
        )

    pipeline = _get_pipeline()
    file_name = os.path.basename(req.file_path)
    file_hash_val = _file_hash(req.file_path)
    state = _load_state()

    # 去重检查
    if file_name in state["files"] and not req.force:
        existing = state["files"][file_name]
        if existing.get("hash") == file_hash_val:
            return IngestResponse(
                file_name=file_name,
                chunks=existing["chunks"],
                status="skipped",
            )

    # 强制更新：先删旧的
    if file_name in state["files"]:
        try:
            pipeline._retriever.delete_by_document(file_name)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"删除旧文档索引失败: {e}",
            ) from e

    # 摄入
    try:
        count = await pipeline.ingest(req.file_path, req.category)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"文件不存在: {req.file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 更新状态
    status = "updated" if file_name in state["files"] else "ok"
    state["files"][file_name] = {
        "hash": file_hash_val,
        "chunks": count,
        "category": req.category,
        "ingested_at": datetime.now().isoformat(),
    }
    _save_state(state)

    return IngestResponse(file_name=file_name, chunks=count, status=status)


@router.get("/list")
async def list_documents():
    """列出所有文档及摄入状态"""
    doc_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")
    state = _load_state()
    files = sorted(glob.glob(os.path.join(doc_dir, "*.md")))

    result = []
    for f in files:
        name = os.path.basename(f)
        info = state["files"].get(name, {})
        result.append({
            "name": name,
            "ingested": name in state["files"],
            "chunks": info.get("chunks", 0),
            "category": info.get("category", ""),
            "ingested_at": info.get("ingested_at", ""),
        })

    return {"count": len(files), "ingested": sum(1 for r in result if r["ingested"]), "documents": result}


@router.get("/status")
async def ingestion_status():
    """摄入状态概览"""
    state = _load_state()
    total = len(state["files"])
    total_chunks = sum(f["chunks"] for f in state["files"].values())
    return {
        "total_ingested": total,
        "total_chunks": total_chunks,
        "last_ingestion": max(
            (f.get("ingested_at", "") for f in state["files"].values()),
            default="",
        ),
    }


@router.delete("/{file_name}")
async def delete_document(file_name: str):
    """删除文档——从 ChromaDB + BM25 索引中移除，不删原文件"""
    pipeline = _get_pipeline()
    state = _load_state()

    if file_name not in state["files"]:
        raise HTTPException(status_code=404, detail=f"文档未摄入: {file_name}")

    count = pipeline._retriever.delete_by_document(file_name)
    del state["files"][file_name]
    _save_state(state)

    return {"file_name": file_name, "deleted_vectors": count, "status": "ok"}


@router.post("/reingest-all")
async def reingest_all():
    """全量重新摄入——清空 ChromaDB + 清空 BM25 + 重新摄入所有文档"""
    pipeline = _get_pipeline()
    doc_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")
    files = sorted(glob.glob(os.path.join(doc_dir, "*.md")))

    # 通过检索器 API 清空 ChromaDB 和内存 BM25，避免删除活动数据库目录。
    pipeline._retriever.clear()

    state = {"files": {}}
    total = 0
    failed = []

    for f in files:
        name = os.path.basename(f)
        try:
            n = await pipeline.ingest(f, category="IBM_Docs")
            total += n
            state["files"][name] = {
                "hash": _file_hash(f),
                "chunks": n,
                "category": "IBM_Docs",
                "ingested_at": datetime.now().isoformat(),
            }
        except Exception as e:
            failed.append({"file": name, "error": str(e)})

    _save_state(state)
    return {
        "total_chunks": total,
        "total_files": len(files),
        "failed": failed,
        "status": "ok",
    }
