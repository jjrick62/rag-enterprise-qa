"""文档管理路由——上传/列表/删除"""
import os
import glob
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/documents", tags=["documents"])


class IngestRequest(BaseModel):
    file_path: str
    category: str = "General"


class IngestResponse(BaseModel):
    file_name: str
    chunks: int
    status: str


def _get_pipeline():
    from main import app
    return app.state.pipeline


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(req: IngestRequest):
    """摄入单篇文档——解析→分块→Embedding→入库"""
    pipeline = _get_pipeline()
    try:
        count = await pipeline.ingest(req.file_path, req.category)
        return IngestResponse(
            file_name=os.path.basename(req.file_path),
            chunks=count,
            status="ok",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"文件不存在: {req.file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_documents():
    """列出 data/documents/ 下所有 .md 文件"""
    doc_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")
    files = glob.glob(os.path.join(doc_dir, "*.md"))
    return {
        "count": len(files),
        "documents": [os.path.basename(f) for f in sorted(files)],
    }
