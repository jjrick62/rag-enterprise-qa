#!/usr/bin/env python
"""首次部署：从 ModelScope 下载 Embedding + Reranker 模型到本地

   HuggingFace 在国内经常连不上，本脚本优先走 ModelScope。
   下载目标：backend/models/（已 gitignored）

   用法：
       python download_models.py          # 下载全部模型
       python download_models.py --check  # 仅检查模型是否存在
"""

import os
import sys
from pathlib import Path

MODEL_CACHE = Path(__file__).resolve().parent / "models"

# 需要下载的模型列表
# 格式: (HuggingFace ID, ModelScope ID, 类别, 用途)
MODELS = [
    (
        "BAAI/bge-small-zh-v1.5",
        "AI-ModelScope/bge-small-zh-v1.5",
        "embedder",
        "中文 Embedding，512 维",
    ),
    (
        "BAAI/bge-reranker-v2-m3",
        "AI-ModelScope/bge-reranker-v2-m3",
        "reranker",
        "跨编码器重排序",
    ),
    # 可选：英文 Embedding
    # ("BAAI/bge-base-en-v1.5", "AI-ModelScope/bge-base-en-v1.5", "embedder", "英文 Embedding，768 维"),
]


def model_exists(hf_id: str) -> bool:
    """检查模型是否已存在于本地缓存"""
    cache_dir = MODEL_CACHE
    # ModelScope 下载后的目录结构: models/AI-ModelScope/<model_name>/
    for path in cache_dir.rglob("config.json"):
        if path.parent.is_dir():
            return True
    # HuggingFace 缓存格式
    for path in cache_dir.rglob("**/snapshots/**/config.json"):
        if path.parent.is_dir():
            return True
    return False


def download_from_modelscope(ms_id: str, hf_id: str, model_type: str):
    """从 ModelScope 下载模型"""
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError:
        print("[ERROR] modelscope 未安装，请先执行: pip install modelscope")
        return False

    model_name = ms_id.split("/")[-1]
    target = MODEL_CACHE / "AI-ModelScope" / model_name

    if target.exists() and any(target.iterdir()):
        print(f"  [SKIP] 已存在: {target}")
        return True

    print(f"  [DOWNLOAD] {ms_id} -> {target}")
    try:
        snapshot_download(
            ms_id,
            cache_dir=str(MODEL_CACHE),
            local_dir=str(target),
        )
        print(f"  [OK] {model_name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {model_name}: {e}")
        return False


def download_from_huggingface(hf_id: str, model_type: str):
    """从 HuggingFace 下载模型（备用方案）"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[ERROR] huggingface_hub 未安装，请先执行: pip install huggingface_hub")
        return False

    model_name = hf_id.split("/")[-1]
    print(f"  [DOWNLOAD] {hf_id} (HuggingFace)")
    try:
        snapshot_download(
            hf_id,
            cache_dir=str(MODEL_CACHE),
            local_files_only=False,
        )
        print(f"  [OK] {model_name}")
        return True
    except Exception as e:
        print(f"  [FAIL] HuggingFace {model_name}: {e}")
        return False


def check_only():
    """仅检查模型是否存在"""
    all_ok = True
    for hf_id, ms_id, mtype, desc in MODELS:
        exists = model_exists(hf_id)
        status = "[OK]" if exists else "[MISSING]"
        print(f"  {status} {hf_id} ({desc})")
        if not exists:
            all_ok = False
    return all_ok


def main():
    if "--check" in sys.argv:
        print("检查模型状态...")
        ok = check_only()
        sys.exit(0 if ok else 1)

    print("=" * 60)
    print("RAG Enterprise QA — 模型下载工具")
    print(f"缓存目录: {MODEL_CACHE}")
    print("=" * 60)

    MODEL_CACHE.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    for hf_id, ms_id, mtype, desc in MODELS:
        print(f"\n[{mtype.upper()}] {hf_id}")
        print(f"  用途: {desc}")

        # 先检查是否已存在
        if model_exists(hf_id):
            print(f"  [SKIP] 模型已存在，跳过下载")
            success += 1
            continue

        # 方案 A: ModelScope（国内优先）
        print("  尝试 ModelScope...")
        if download_from_modelscope(ms_id, hf_id, mtype):
            success += 1
            continue

        # 方案 B: HuggingFace（备用）
        print("  尝试 HuggingFace...")
        if download_from_huggingface(hf_id, mtype):
            success += 1
            continue

        failed += 1

    print("\n" + "=" * 60)
    print(f"下载完成: {success} 成功, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        print("\n[WARN] 部分模型下载失败。可尝试：")
        print("  1. 手动从 ModelScope 下载: https://modelscope.cn")
        print("  2. 设置 HF 镜像: set HF_ENDPOINT=https://hf-mirror.com")
        print("  3. 重新运行: python download_models.py")


if __name__ == "__main__":
    main()
