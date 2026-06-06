"""RagasEvaluator — 正统 RAGAS 框架 OOP 封装

继承 BaseEvaluator，实现 RAGAS 两步法评估。
独立 venv (venv_ragas) 运行，避免跟项目依赖冲突。

架构:
  BaseEvaluator(ABC)
    └─ RagasEvaluator          ← 本文件（RAGAS 正统实现）
    └─ LLMJudgeEvaluator       ← evaluation.py（自研实现，零额外依赖）
"""
import sys, os, json, asyncio
from typing import List, Dict
from dataclasses import dataclass, field
from services.base import BaseEvaluator


@dataclass
class EvalSample:
    question: str
    ground_truth: str = ""
    answer: str = ""
    contexts: List[str] = field(default_factory=list)


@dataclass
class EvalReport:
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    per_sample: List[Dict] = field(default_factory=list)
    summary: str = ""


def prepare_evaluation_dataset(dataset: List[Dict]) -> List[Dict]:
    """Copy evaluation samples without changing the evidence seen by the generator."""
    prepared = []
    for sample in dataset:
        copied = dict(sample)
        copied["contexts"] = list(sample.get("contexts", []))
        prepared.append(copied)
    return prepared


class RagasEvaluator(BaseEvaluator):
    """RAGAS 两步法评估器

    Faithfulness 流程:
      Step 1: LLM 把回答拆成原子声明 (claims)
      Step 2: LLM 逐条核验每个 claim 是否能在上下文中找到依据
      Score = 核验通过的 claims / 总 claims

    跟自研 LLMJudgeEvaluator 的区别:
      - RAGAS: 两步法，评分更精确
      - LLMJudge: 一步法，整体打分
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1",
                 embedding_model: str = "BAAI/bge-small-zh-v1.5",
                 embedding_device: str = "cpu"):
        self._api_key = api_key
        self._base_url = base_url
        self._embedding_model = embedding_model
        self._embedding_device = embedding_device

    async def evaluate(self, dataset: List[Dict]) -> EvalReport:
        """RAGAS 全量评估"""
        if not dataset:
            return EvalReport(summary="Empty dataset")

        from datasets import Dataset
        hf_dataset = Dataset.from_list(prepare_evaluation_dataset(dataset))

        # LLM-as-Judge: 通过 LLM 工厂获取，Monkey-patch 注入 extra_body
        from ragas.llms import llm_factory
        from services.llm_factory import get_provider
        provider = get_provider("judge")
        client = provider.create_client()

        _orig_create = client.chat.completions.create
        def _patched_create(*args, **kwargs):
            kwargs.setdefault('extra_body', {})
            kwargs['extra_body'].update(provider.extra_body)
            return _orig_create(*args, **kwargs)
        client.chat.completions.create = _patched_create

        llm = llm_factory(provider.model, client=client, temperature=0.0, max_tokens=8192)

        # Embeddings: 用本地 BGE 模型，不调 DeepSeek（它没有 /embeddings 端点）
        from services.embedder import BGEBaaIEmbedder
        from ragas.embeddings.base import BaseRagasEmbeddings

        class BGERagasEmbeddings(BaseRagasEmbeddings):
            """本地 BGE 模型包装为 RAGAS embeddings 接口"""
            def __init__(self, model_name, device):
                super().__init__()
                self._bge = BGEBaaIEmbedder(
                    model_name=model_name, device=device, cache_folder="./models",
                )
            def embed_query(self, text: str) -> list:
                return self._bge.embed([text])[0].tolist()
            def embed_documents(self, texts: list) -> list:
                return self._bge.embed(texts).tolist()
            async def aembed_query(self, text: str):
                return self.embed_query(text)
            async def aembed_documents(self, texts: list):
                return self.embed_documents(texts)

        lc_embeddings = BGERagasEmbeddings(self._embedding_model, self._embedding_device)

        # RAGAS 0.4 兼容方案：旧版 singleton 指标
        from ragas.metrics import faithfulness, answer_relevancy, context_precision  # noqa: E402
        faithfulness.llm = llm
        answer_relevancy.llm = llm
        answer_relevancy.embeddings = lc_embeddings
        context_precision.llm = llm

        from ragas import evaluate as ragas_evaluate  # noqa: E402
        result = ragas_evaluate(
            dataset=hf_dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
        )

        # 提取分数
        scores = result.to_pandas().to_dict(orient="records") if hasattr(result, 'to_pandas') else {}

        # 计算均值
        df = result.to_pandas()
        report = EvalReport(
            faithfulness=round(float(df["faithfulness"].mean()), 3),
            answer_relevancy=round(float(df["answer_relevancy"].mean()), 3) if "answer_relevancy" in df else 0.0,
            context_precision=round(float(df["context_precision"].mean()), 3),
            context_recall=0.0,  # 本次评估未启用
            per_sample=df.to_dict(orient="records"),
            summary=self._make_summary(df),
        )
        return report

    def _make_summary(self, df) -> str:
        faith = float(df["faithfulness"].mean())
        rel = float(df["answer_relevancy"].mean())
        prec = float(df["context_precision"].mean())

        level = (
            "生产就绪" if faith >= 0.80 and rel >= 0.80
            else "接近生产" if faith >= 0.70
            else "demo 级别"
        )
        return (
            f"综合评级 (RAGAS): {level}\n"
            f"Faithfulness={faith:.3f} | AnswerRelevancy={rel:.3f} | "
            f"ContextPrecision={prec:.3f}"
        )
