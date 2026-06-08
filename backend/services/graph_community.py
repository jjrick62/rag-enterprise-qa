"""Graph RAG 社区管理——聚类检测 + 摘要生成

流程:
  1. 基于实体共现关系做社区检测（简单连通分量 → 正式版上 Leiden）
  2. 收集每个社区内的文档内容
  3. 用 LLM 为每个社区生成摘要
  4. 摘要存入 Embedding 库，查询时先匹配社区再下钻
"""
import json
import os
from typing import List, Dict, Set
from dataclasses import dataclass, field
from services.graph_builder import KnowledgeGraph


@dataclass
class Community:
    community_id: str
    entities: List[str]        # 社区内的实体
    doc_ids: Set[str]          # 关联的文档
    summary: str = ""          # LLM 生成的社区摘要


@dataclass
class CommunityIndex:
    communities: List[Community] = field(default_factory=list)

    def find_relevant(self, query: str, top_k: int = 3) -> List[Community]:
        """简单关键词匹配找相关社区（后续用 Embedding 检索摘要替代）"""
        query_lower = query.lower()
        scored = []
        for c in self.communities:
            score = 0
            for ent in c.entities:
                if ent.lower() in query_lower or query_lower in ent.lower():
                    score += 1
            if c.summary and any(w in c.summary.lower() for w in query_lower.split()):
                score += 2
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def to_dict(self) -> dict:
        return {
            "communities": [
                {
                    "id": c.community_id,
                    "entities": c.entities,
                    "doc_ids": list(c.doc_ids),
                    "summary": c.summary,
                }
                for c in self.communities
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CommunityIndex":
        ci = cls()
        for c in data["communities"]:
            ci.communities.append(Community(
                community_id=c["id"],
                entities=c["entities"],
                doc_ids=set(c["doc_ids"]),
                summary=c.get("summary", ""),
            ))
        return ci


SUMMARY_PROMPT = """你是技术文档分析助手。以下是知识库中一个主题集群包含的实体和文档。

## 实体列表
{entities}

## 包含的文档
{doc_list}

## 任务
基于以上信息，写一段 3-5 句话的中文摘要，说明：
1. 这个主题集群主要讲什么
2. 包含哪些核心技术/产品/概念
3. 适合回答什么类型的问题

请直接输出摘要，不要加标题。"""


class CommunityBuilder:
    """社区构建器——检测 + 摘要"""

    def __init__(self, provider):
        self._client = provider.create_async_client()
        self._model = provider.model
        self._extra_body = provider.extra_body

    def detect_communities(self, kg: KnowledgeGraph) -> List[Community]:
        """基于实体共现关系做简单的连通分量检测

        正式版应该用 Leiden/Louvain 算法。当前用简单的双向关系遍历。
        """
        # 构建邻接表（实体 → 相邻实体）
        adj: Dict[str, Set[str]] = {}
        for r in kg.relations:
            adj.setdefault(r.source, set()).add(r.target)
            adj.setdefault(r.target, set()).add(r.source)

        # 连通分量检测
        visited: Set[str] = set()
        communities: List[Community] = []
        cid = 0

        for entity in kg.entities:
            if entity in visited:
                continue
            # BFS 收集连通分量
            component: Set[str] = set()
            queue = [entity]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                for neighbor in adj.get(node, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)

            # 收集该分量内的文档
            doc_ids: Set[str] = set()
            for ent in component:
                if ent in kg.entities:
                    doc_ids.update(kg.entities[ent].doc_ids)

            cid += 1
            communities.append(Community(
                community_id=f"community_{cid}",
                entities=sorted(component),
                doc_ids=doc_ids,
            ))

        return communities

    async def generate_summary(
        self, community: Community,
        doc_paths: Dict[str, str],
    ) -> str:
        """为一个社区生成摘要"""
        entities_str = ", ".join(community.entities[:30])
        doc_names = [
            os.path.basename(p).replace(".md", "").replace("_", " ")[:60]
            for p in community.doc_ids
            if p in doc_paths
        ][:20]
        doc_list = "\n".join(f"- {d}" for d in doc_names) if doc_names else "（无文档清单）"

        prompt = SUMMARY_PROMPT.format(
            entities=entities_str,
            doc_list=doc_list,
        )

        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                extra_body=self._extra_body or None,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return f"社区包含 {len(community.entities)} 个实体和 {len(community.doc_ids)} 篇文档"

    def save(self, ci: CommunityIndex, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(ci.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, filepath: str) -> CommunityIndex:
        with open(filepath, "r", encoding="utf-8") as f:
            return CommunityIndex.from_dict(json.load(f))
