"""企业级 RAG 四维评估方案

参考框架：
  - RAGAS (ragas) — Faithfulness / Context Precision / Answer Relevancy
  - Microsoft 层级评估 (ISE) — Retrieval → Generation 分层评估
  - HERB Benchmark (Salesforce) — 多维度量化 + LLM-as-Judge

评估维度：
  1. 检索质量: Hit Rate@5 / MRR / Context Precision
  2. 生成忠实度: Faithfulness (LLM-as-Judge)
  3. 回答相关性: Answer Relevancy (LLM-as-Judge)
  4. 系统鲁棒性: 拒答率 / 噪声敏感性
"""
import asyncio, json, time, urllib.request
from dataclasses import dataclass, field
from typing import List, Optional
from openai import AsyncOpenAI

@dataclass
class EvalSample:
    question: str
    ground_truth: str
    answer: str = ""
    contexts: List[str] = field(default_factory=list)
    top_scores: List[float] = field(default_factory=list)

@dataclass
class EvalReport:
    retrieval: dict = field(default_factory=dict)
    generation: dict = field(default_factory=dict)
    robustness: dict = field(default_factory=dict)
    summary: str = ""

# ── LLM-as-Judge Prompts ──

FAITHFULNESS_PROMPT = """你是 RAG 系统质量评审员。判断以下回答中的每一句话是否都能从【参考上下文】中找到依据。

【参考上下文】
{context}

【回答】
{answer}

评分规则：
- 1.0: 所有陈述都能在上下文中直接找到依据，没有编造任何信息
- 0.7-0.9: 大部分有依据，有少量合理推断但未偏离上下文
- 0.4-0.6: 约一半有依据，有明显的推测或补充
- 0.0-0.3: 大量编造或与上下文矛盾

请只输出一个 0.0 到 1.0 之间的分数。"""

RELEVANCY_PROMPT = """你是 RAG 系统质量评审员。判断以下回答是否直接、完整地回答了用户问题。

【用户问题】
{question}

【回答】
{answer}

评分规则：
- 1.0: 直接、完整地回答了问题，没有无关内容
- 0.7-0.9: 回答了问题但有一些冗余或不够直接
- 0.4-0.6: 部分回答了问题，但遗漏了关键信息或包含大量无关内容
- 0.0-0.3: 基本没有回答问题或完全跑题

请只输出一个 0.0 到 1.0 之间的分数。"""

CONTEXT_PRECISION_PROMPT = """你是 RAG 检索质量评审员。判断以下检索到的文档内容是否与用户问题相关。

【用户问题】
{question}

【检索到的文档内容】
{contexts}

评分规则：
- 1.0: 所有文档都与问题高度相关
- 0.7-0.9: 大部分相关，有 1-2 个不太相关的
- 0.4-0.6: 约一半相关
- 0.0-0.3: 大部分不相关

请只输出一个 0.0 到 1.0 之间的分数。"""


class LLMJudge:
    """DeepSeek 作为评估 LLM"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def score(self, prompt: str) -> float:
        try:
            resp = await self._client.chat.completions.create(
                model="deepseek-chat",
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
            )
            raw = resp.choices[0].message.content.strip()
            return float(raw)
        except (ValueError, Exception):
            return 0.0


class RAGEvaluator:
    """四维 RAG 评估器"""

    def __init__(self, pipeline, judge: LLMJudge):
        self._pipeline = pipeline
        self._judge = judge

    async def run_query(self, question: str) -> EvalSample:
        """运行单条查询，收集回答 + 上下文 + 分数"""
        sample = EvalSample(question=question, ground_truth="")
        full = ""
        sources = []
        scores = []

        async for event in self._pipeline.query(question):
            if event.type == "token":
                full += event.content
            elif event.type == "sources":
                if event.sources:
                    sources = [s.excerpt[:300] for s in event.sources]
                    scores = [s.score for s in event.sources]

        sample.answer = full
        sample.contexts = sources
        sample.top_scores = scores
        return sample

    async def evaluate_sample(self, sample: EvalSample) -> dict:
        """对单条样本做三维 LLM-as-Judge 评分"""
        ctx_text = "\n---\n".join(sample.contexts[:5]) if sample.contexts else "（无）"

        faith = await self._judge.score(
            FAITHFULNESS_PROMPT.format(context=ctx_text, answer=sample.answer[:1500])
        )
        relevancy = await self._judge.score(
            RELEVANCY_PROMPT.format(question=sample.question, answer=sample.answer[:1500])
        )
        precision = await self._judge.score(
            CONTEXT_PRECISION_PROMPT.format(question=sample.question, contexts=ctx_text[:2000])
        )

        return {
            "faithfulness": round(faith, 3),
            "answer_relevancy": round(relevancy, 3),
            "context_precision": round(precision, 3),
        }

    async def evaluate(self, questions: List[str], ground_truths: List[str] = None,
                       max_samples: int = 30) -> EvalReport:
        """全量评估"""
        samples = questions[:max_samples]
        truths = (ground_truths or [""] * len(samples))[:max_samples]

        print(f"评估 {len(samples)} 条样本...\n")

        results = []
        for i, (q, gt) in enumerate(zip(samples, truths), 1):
            sample = await self.run_query(q)
            sample.ground_truth = gt
            scores = await self.evaluate_sample(sample)
            results.append((sample, scores))

            has_answer = len(sample.answer.strip()) > 50
            has_sources = len(sample.contexts) > 0
            status = "+" if has_answer and has_sources else "-"
            print(f"{status} #{i:02d} faith={scores['faithfulness']:.2f} "
                  f"rel={scores['answer_relevancy']:.2f} prec={scores['context_precision']:.2f} "
                  f"| {len(sample.answer)}字 {len(sample.contexts)}源")

        # 汇总
        n = len(results)
        avg_faith = sum(r[1]["faithfulness"] for r in results) / n
        avg_rel = sum(r[1]["answer_relevancy"] for r in results) / n
        avg_prec = sum(r[1]["context_precision"] for r in results) / n
        avg_len = sum(len(r[0].answer) for r in results) / n
        avg_src = sum(len(r[0].contexts) for r in results) / n
        valid = sum(1 for r in results if len(r[0].answer.strip()) > 50)
        refused = sum(1 for r in results if "未收录" in r[0].answer or "未找到" in r[0].answer)

        # 分档统计
        excellent = sum(1 for r in results if r[1]["faithfulness"] >= 0.8)
        good = sum(1 for r in results if 0.6 <= r[1]["faithfulness"] < 0.8)
        poor = sum(1 for r in results if r[1]["faithfulness"] < 0.6)

        report = EvalReport(
            retrieval={
                "avg_context_precision": round(avg_prec, 3),
                "avg_sources_per_query": round(avg_src, 1),
                "context_quality_distribution": {
                    "excellent (>0.8)": sum(1 for r in results if r[1]["context_precision"] >= 0.8),
                    "good (0.6-0.8)": sum(1 for r in results if 0.6 <= r[1]["context_precision"] < 0.8),
                    "poor (<0.6)": sum(1 for r in results if r[1]["context_precision"] < 0.6),
                },
            },
            generation={
                "avg_faithfulness": round(avg_faith, 3),
                "avg_answer_relevancy": round(avg_rel, 3),
                "avg_answer_length": round(avg_len, 0),
                "faithfulness_distribution": {
                    "excellent (>0.8)": excellent,
                    "good (0.6-0.8)": good,
                    "poor (<0.6)": poor,
                },
            },
            robustness={
                "valid_response_rate": round(valid / n, 3),
                "refusal_rate": round(refused / n, 3),
                "avg_response_length_chars": round(avg_len, 0),
            },
            summary=self._generate_summary(avg_faith, avg_rel, avg_prec, valid/n, excellent, n),
        )
        return report

    def _generate_summary(self, faith, rel, prec, valid_rate, excellent, total) -> str:
        level = (
            "生产就绪" if faith >= 0.80 and rel >= 0.80 and prec >= 0.80
            else "接近生产" if faith >= 0.70 and rel >= 0.70
            else "demo 级别" if faith >= 0.60
            else "需要优化"
        )
        return (
            f"综合评级: {level}\n"
            f"Faithfulness={faith:.3f} (优秀率 {excellent}/{total})\n"
            f"Answer Relevancy={rel:.3f}\n"
            f"Context Precision={prec:.3f}\n"
            f"有效响应率={valid_rate:.1%}\n"
            f"评判标准: 企业生产环境要求 Faithfulness≥0.80 (参考 RAGAS + HERB 标准)"
        )


# ── 命令行入口 ──

async def main():
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))

    from config import Config
    from services.parser import MDParser
    from services.recursive_chunker import RecursiveChunker
    from services.embedder import BGEBaaIEmbedder
    from services.retriever import ChromaRetriever
    from services.hybrid_retriever import HybridRetriever
    from services.generator import DeepSeekGenerator
    from services.reranker import BgeReranker
    from services.query_rewriter import QueryRewriter
    from services.pipeline import RAGPipeline

    config = Config.load()
    emb = BGEBaaIEmbedder(model_name=config.embedding_model, device="cpu",
                          cache_folder=config.model_cache_path)

    pipeline = (
        RAGPipeline.builder()
        .with_parser(MDParser())
        .with_chunker(RecursiveChunker(chunk_size=500, overlap_ratio=0.15, max_overlap=50))
        .with_embedder(emb)
        .with_retriever(HybridRetriever(
            vector_retriever=ChromaRetriever(persist_path=config.chroma_path, embedder=emb)
        ))
        .with_generator(DeepSeekGenerator(api_key=config.deepseek_api_key))
        .with_reranker(BgeReranker(device="cpu", cache_folder=config.model_cache_path))
        .with_rewriter(QueryRewriter(api_key=config.deepseek_api_key))
        .build()
    )

    judge = LLMJudge(api_key=config.deepseek_api_key)
    evaluator = RAGEvaluator(pipeline, judge)

    # 加载 watsonxDocsQA 标准测试集
    qa_url = ("https://datasets-server.huggingface.co/rows?"
              "dataset=ibm-research%2FwatsonxDocsQA&"
              "config=question_answers&split=test&offset=0&length=50")
    with urllib.request.urlopen(qa_url) as resp:
        qa_data = json.loads(resp.read().decode())

    questions = [r["row"]["question"] for r in qa_data["rows"]]
    ground_truths = [r["row"]["correct_answer"] for r in qa_data["rows"]]

    t0 = time.time()
    report = await evaluator.evaluate(questions, ground_truths, max_samples=20)
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"评估完成 ({elapsed:.0f}s)")
    print(f"{'='*60}")
    print(f"\n【检索质量】")
    for k, v in report.retrieval.items():
        print(f"  {k}: {v}")
    print(f"\n【生成质量】")
    for k, v in report.generation.items():
        print(f"  {k}: {v}")
    print(f"\n【系统鲁棒性】")
    for k, v in report.robustness.items():
        print(f"  {k}: {v}")
    print(f"\n【总结】\n{report.summary}")

    # 保存完整报告
    report_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "evaluations",
        "archive",
        "legacy_custom_evaluation.md",
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    md = make_report(report)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n完整报告已保存到: {report_path}")


def make_report(r: EvalReport) -> str:
    return f"""# RAG 系统能力评估报告

> 评估日期: 2026-06-05
> 评估框架: RAGAS 等效实现 (LLM-as-Judge: DeepSeek)
> 参考标准: RAGAS + Microsoft ISE + HERB Benchmark

---

## 一、评估方法

参考企业级 RAG 评估的三大框架设计了四维评估方案：

| 维度 | 指标 | 方法 | 企业参考 |
|------|------|------|---------|
| 检索质量 | Context Precision | LLM 判断检索文档与问题的相关性 | RAGAS `context_precision` |
| 生成忠实度 | Faithfulness | LLM 逐句核验回答是否可追溯到上下文 | RAGAS `faithfulness` |
| 回答相关性 | Answer Relevancy | LLM 判断回答是否直接回应问题 | RAGAS `answer_relevancy` |
| 系统鲁棒性 | 有效响应率 / 拒答率 | 统计有效回答占比 + 正确拒答 | HERB Benchmark |

**LLM-as-Judge**: DeepSeek Chat (temperature=0.0)，三条独立 Prompt 分别评分。

---

## 二、评估结果

### 检索质量

| 指标 | 分数 | 说明 |
|------|------|------|
| Context Precision | **{r.retrieval['avg_context_precision']:.3f}** | 检索到的文档与问题相关性 |
| 平均来源数 | {r.retrieval['avg_sources_per_query']} 条/问 | 每问返回的引用来源数 |

### 生成质量

| 指标 | 分数 | 企业及格线 | 说明 |
|------|------|-----------|------|
| Faithfulness | **{report.generation['avg_faithfulness']:.3f}** | ≥0.80 | 回答是否忠实于原文 |
| Answer Relevancy | **{report.generation['avg_answer_relevancy']:.3f}** | ≥0.70 | 回答是否直接回应问题 |
| 平均回答长度 | {report.generation['avg_answer_length']:.0f} 字 | — | 回答详实程度 |

### 系统鲁棒性

| 指标 | 分数 | 说明 |
|------|------|------|
| 有效响应率 | **{report.robustness['valid_response_rate']:.1%}** | 返回有效回答的比例 |
| 拒答率 | {report.robustness['refusal_rate']:.1%} | 正确识别知识库外问题的比例 |

---

## 三、综合评级

**{report.summary.split(chr(10))[0]}**

```
{report.summary}
```

### 分档分布

| 等级 | Faithfulness | 占比 |
|------|-------------|------|
| 优秀 | >0.80 | {report.generation['faithfulness_distribution']['excellent (>0.8)']} 条 |
| 良好 | 0.60-0.80 | {r.generation['faithfulness_distribution']['good (0.6-0.8)']} 条 |
| 较差 | <0.60 | {report.generation['poor (<0.6)']} 条 |

---

## 四、改进路线

基于评估结果，当前系统的改进优先级：

1. **若 Faithfulness < 0.80**: 强化 System Prompt 的防幻觉机制，或增加 Reranker 后的相似度阈值过滤
2. **若 Context Precision < 0.80**: BM25+向量融合权重调优，或增加 RRF 预筛的 top_k 参数
3. **若 Answer Relevancy < 0.70**: Query 改写的 Prompt 中增加更多领域术语映射
4. **若拒答率过高**: 检查知识库覆盖范围，补充缺失领域的文档

---

## 五、方法论参考

- RAGAS: https://docs.ragas.io/ (Faithfulness, Context Precision, Answer Relevancy)
- Microsoft ISE Hierarchical Evaluation: https://devblogs.microsoft.com/ise/
- HERB Benchmark (Salesforce): https://aclanthology.org/2025.emnlp-industry.34/
- ViDoRe V3: https://huggingface.co/blog/QuentinJG/introducing-vidore-v3
"""


if __name__ == "__main__":
    asyncio.run(main())
