"""Graph RAG 检索器——图谱感知的文档检索

两种查询模式：
  local query:  精准实体寻址 → 找关联文档 → 送 Hybrid 检索
  global query: 社区摘要匹配 → 下钻社区 chunks → 送 Hybrid 检索
"""
from typing import List, Optional
from services.graph_builder import KnowledgeGraph
from services.graph_community import CommunityIndex


class GraphRetriever:
    """图谱增强检索器

    在 Hybrid 检索前加一层图谱过滤——
    local: 问题匹配到实体 → 限定在该实体相关文档中检索
    global: 问题匹配到社区摘要 → 在社区文档集合中检索
    """

    def __init__(self, kg: KnowledgeGraph, ci: CommunityIndex):
        self._kg = kg
        self._ci = ci

    def analyze_query(self, query: str) -> dict:
        """分析查询类型 + 匹配的实体/社区

        Returns:
          {"type": "local"|"global", "entities": [...], "communities": [...], "related_docs": [...]}
        """
        query_lower = query.lower()
        matched_entities = []
        matched_communities = []

        # 实体匹配（模糊子串匹配）
        for name, entity in self._kg.entities.items():
            if name in query_lower or any(
                word in query_lower for word in name.split()
                if len(word) > 3
            ):
                matched_entities.append({
                    "name": name,
                    "type": entity.entity_type,
                    "doc_ids": list(entity.doc_ids),
                })

        # 社区匹配
        matched_communities = [
            {"id": c.community_id, "entities": c.entities[:10],
             "summary": c.summary, "doc_ids": list(c.doc_ids)}
            for c in self._ci.find_relevant(query, top_k=2)
        ]

        # 判断查询类型
        if matched_entities and not matched_communities:
            query_type = "local"
        elif matched_communities and not matched_entities:
            query_type = "global"
        elif matched_entities and matched_communities:
            query_type = "local"  # 有实体命中优先 local
        else:
            query_type = "global"  # 都没命中走全局（fallback 到正常检索）

        # 收集相关文档
        related_docs = set()
        for ent in matched_entities:
            related_docs.update(ent["doc_ids"])
        for com in matched_communities:
            related_docs.update(com["doc_ids"])

        return {
            "type": query_type,
            "entities": matched_entities,
            "communities": matched_communities,
            "related_docs": list(related_docs),
        }

    def get_entity_context(self, entity_name: str) -> Optional[str]:
        """获取实体的上下文信息——关联实体 + 关系"""
        name = entity_name.strip().lower()
        if name not in self._kg.entities:
            return None

        entity = self._kg.entities[name]
        related = [
            r for r in self._kg.relations
            if r.source == name or r.target == name
        ][:10]

        lines = [f"Entity: {name} ({entity.entity_type})"]
        lines.append(f"Mentioned in {len(entity.doc_ids)} documents")
        if related:
            lines.append("Relations:")
            for r in related:
                other = r.target if r.source == name else r.source
                lines.append(f"  - {r.relation_type}: {other} ({r.description[:80]})")

        return "\n".join(lines)
