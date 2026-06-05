"""Graph RAG 图谱构建器——实体抽取 + 关系建模

预处理阶段（离线）：
  1. 用 LLM 从每篇文档抽取实体（技术名词、API、产品、概念）
  2. 跨文档链接同名/同义实体
  3. 构建实体-文档映射 + 实体关系网络
"""
import json
import os
import asyncio
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, field
from openai import AsyncOpenAI


@dataclass
class Entity:
    name: str              # 实体名称（如 "watsonx.ai", "CPLEX", "Federated Learning"）
    entity_type: str        # 类型（platform/api/concept/product/parameter）
    doc_ids: Set[str] = field(default_factory=set)  # 包含此实体的文档列表


@dataclass
class Relation:
    source: str             # 源实体名
    target: str             # 目标实体名
    relation_type: str      # 关系类型（depends_on/part_of/uses/alternative_to）
    description: str        # 关系描述


@dataclass
class KnowledgeGraph:
    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)

    def add_entity(self, name: str, entity_type: str, doc_id: str):
        name = name.strip().lower()
        if name in self.entities:
            self.entities[name].doc_ids.add(doc_id)
        else:
            self.entities[name] = Entity(
                name=name, entity_type=entity_type, doc_ids={doc_id}
            )

    def add_relation(self, source: str, target: str, rel_type: str, desc: str):
        self.relations.append(Relation(
            source=source.strip().lower(),
            target=target.strip().lower(),
            relation_type=rel_type,
            description=desc,
        ))

    def to_dict(self) -> dict:
        return {
            "entities": {
                name: {"type": e.entity_type, "doc_ids": list(e.doc_ids)}
                for name, e in self.entities.items()
            },
            "relations": [
                {"source": r.source, "target": r.target,
                 "type": r.relation_type, "desc": r.description}
                for r in self.relations
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeGraph":
        kg = cls()
        for name, info in data["entities"].items():
            kg.entities[name] = Entity(
                name=name, entity_type=info["type"],
                doc_ids=set(info["doc_ids"])
            )
        for r in data.get("relations", []):
            kg.relations.append(Relation(
                source=r["source"], target=r["target"],
                relation_type=r["type"], description=r["desc"]
            ))
        return kg


EXTRACTION_PROMPT = """你是知识图谱构建助手。从以下文档内容中提取关键实体和它们之间的关系。

## 实体类型
- platform: 平台/产品（如 watsonx.ai, Watson Machine Learning）
- api: API/接口（如 REST API, Python client）
- concept: 技术概念（如 Federated Learning, tokenization）
- parameter: 参数/配置项（如 temperature, top_p）
- tool: 工具/求解器（如 CPLEX, CPO, OPL）

## 输出格式（严格遵守——所有 key 和字符串必须用双引号）
{{"entities": [{{"name": "实体名", "type": "类型"}}], "relations": [{{"source": "源实体", "target": "目标实体", "type": "depends_on|part_of|uses", "desc": "关系描述"}}]}}

## 规则
- 只提取有实际意义的实体，忽略"the", "this" 等通用词
- 最多提取 10 个实体
- 每个实体只提取一次，不要重复
- 输出必须是可被 JSON.parse 解析的有效 JSON，key 必须用双引号包裹

## 文档内容
{document}

输出（仅 JSON，不要包裹在 ``` 中）:"""


class GraphBuilder:
    """知识图谱构建器——调用 LLM 抽取实体和关系"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._kg = KnowledgeGraph()

    @property
    def graph(self) -> KnowledgeGraph:
        return self._kg

    async def extract_from_document(self, doc_content: str, doc_id: str):
        """从单篇文档抽取实体和关系"""
        prompt = EXTRACTION_PROMPT.format(document=doc_content[:3000])

        try:
            resp = await self._client.chat.completions.create(
                model="deepseek-chat",
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )
            raw = resp.choices[0].message.content
            # 清理 markdown 代码块包裹
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]  # 去掉 ```json
                if raw.endswith("```"):
                    raw = raw[:-3]
            data = json.loads(raw.strip())

            for ent in data.get("entities", []):
                self._kg.add_entity(ent["name"], ent["type"], doc_id)

            for rel in data.get("relations", []):
                self._kg.add_relation(
                    rel["source"], rel["target"],
                    rel.get("type", "related_to"),
                    rel.get("desc", ""),
                )
        except json.JSONDecodeError as e:
            # 打印原始响应帮助调试
            preview = raw[:200] if 'raw' in dir() else ""
            print(f"  JSON error for {doc_id[:40]}: {e}")
        except Exception as e:
            print(f"  Graph extraction failed for {doc_id[:40]}: {e}")

    async def build_from_documents(self, doc_paths: List[str]):
        """批量构建图谱——逐篇处理"""
        total = len(doc_paths)
        for i, path in enumerate(doc_paths, 1):
            doc_id = os.path.basename(path).replace(".md", "")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                await self.extract_from_document(content, doc_id)
                if i % 10 == 0:
                    print(f"  Graph: {i}/{total} docs, {len(self._kg.entities)} entities")
            except Exception as e:
                print(f"  Skip {doc_id}: {e}")

    def save(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._kg.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            self._kg = KnowledgeGraph.from_dict(json.load(f))
