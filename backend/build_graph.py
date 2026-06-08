"""Graph RAG 图谱构建脚本

离线运行——从文档中抽取实体/关系 → 社区检测 → 摘要生成 → 持久化
"""
import asyncio
import os
import glob
import sys

# 确保 backend 在 path
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from services.graph_builder import GraphBuilder
from services.graph_community import CommunityBuilder, CommunityIndex
from services.llm_factory import get_provider


async def main(sample_size: int = 0):
    """构建知识图谱

    Args:
        sample_size: 0 = 全量 54 篇，N = 只处理 N 篇（快速测试）
    """
    config = Config.load()
    doc_dir = os.path.join(os.path.dirname(__file__), "..", "data", "documents")
    files = sorted(glob.glob(os.path.join(doc_dir, "*.md")))

    if sample_size > 0:
        files = files[:sample_size]

    graph_path = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_graph.json")
    community_path = os.path.join(os.path.dirname(__file__), "..", "data", "community_index.json")

    print(f"=== Graph RAG 图谱构建: {len(files)} 篇文档 ===\n")

    # Step 1: 实体/关系抽取
    print("[1/3] 抽取实体和关系...")
    provider = get_provider("generate")
    builder = GraphBuilder(provider=provider)
    await builder.build_from_documents(files)
    builder.save(graph_path)
    kg = builder.graph
    print(f"  Entities: {len(kg.entities)}, Relations: {len(kg.relations)}")

    # Step 2: 社区检测
    print("\n[2/3] 社区检测...")
    cb = CommunityBuilder(provider=provider)
    communities = cb.detect_communities(kg)
    print(f"  Communities: {len(communities)}")

    ci = CommunityIndex(communities=communities)

    # Step 3: 生成社区摘要
    print("\n[3/3] 生成社区摘要...")
    doc_path_map = {os.path.basename(f).replace(".md", ""): f for f in files}

    for i, community in enumerate(ci.communities, 1):
        summary = await cb.generate_summary(community, doc_path_map)
        community.summary = summary
        if i % 5 == 0:
            print(f"  {i}/{len(ci.communities)} summaries generated")
        # 小延迟避免 API 限流
        if i < len(ci.communities):
            await asyncio.sleep(0.3)

    cb.save(ci, community_path)
    print(f"\n  All {len(ci.communities)} communities summarized")
    print(f"\n  Graph saved to: {graph_path}")
    print(f"  Communities saved to: {community_path}")

    # 打印概览
    print("\n=== 图谱概览 ===")
    for c in ci.communities[:5]:
        print(f"  [{c.community_id}] {len(c.entities)} entities, {len(c.doc_ids)} docs")
        print(f"    Summary: {c.summary[:120]}...")
        print()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(main(sample_size=n))
