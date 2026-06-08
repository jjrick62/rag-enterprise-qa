"""Query 改写器——用 LLM 把用户问题转为专业检索词

解决痛点：中文提问、口语化表述、术语不匹配 → Embedding 检索效果差
方案：LLM 看到全库文档索引后，用知识库术语改写问题
"""
from schemas.chat import RetrievalResult

# 全库文档索引——54 篇 IBM watsonx 文档的主题分组
# Query 改写时拼入 Prompt，让 LLM 知道知识库的领域和术语
DOC_INDEX = """【知识库索引 — 54 篇 IBM watsonx 技术文档】

- Foundation Models (19 篇): prompt templates, tokenization, greedy decoding,
  foundation model parameters, tuning experiments, trust calibration,
  supported models (flan-t5, granite, llama-2, mpt, starcoder)

- Decision Optimization (21 篇): CPLEX, CPO, OPL, Java worker, Python DOcplex,
  model deployment (UI + REST API), solve parameters, experiments,
  Modeling Assistant, visualization, scenarios, data sources

- Federated Learning (2 篇): architecture, experiment workflow, benefits

- Platform & Security (4 篇): IBM Cloud account security, service ID,
  asset search, glossary

- Database Connections (3 篇): IBM Db2 for z/OS, Microsoft SQL Server, Box

- Geospatial Analysis (2 篇): geospatial library functions, map charts

- SPSS Modeler (2 篇): Bayes Net node, Sim Eval node, CLEM parameters,
  Flow and SuperNode parameters

- Other (1 篇): generating accurate output

关键术语映射:
  "foundation models" = 基础模型, "prompt template" = 提示模板,
  "federated learning" = 联邦学习, "decision optimization" = 决策优化,
  "deployment" = 部署, "tokenization" = 分词,
  "CPLEX/CPO/OPL" = IBM 优化求解器, "DOcplex" = Python 建模 API"""

REWRITE_SYSTEM = """你是 RAG 检索系统的 Query 优化器。你的任务是把用户的原始问题改写为适合向量检索的专业英文查询。

{index}

## 改写规则
1. 如果用户用中文提问，翻译为英文（知识库全是英文文档）
2. 用知识库中的专业术语替换用户的通俗表述
3. 删除无关的礼貌用语、语气词，只保留核心检索意图
4. 保持原问题的语义完整，不要添加问题中没有的信息
5. 输出只包含改写后的问题，不要加引号、解释、前缀

## 示例
输入: "有啥基础模型能用"        → What foundation models are available in watsonx.ai
输入: "怎么部署模型"            → How to deploy a Decision Optimization model
输入: "联邦学习是干啥的"        → What is IBM Federated Learning and its architecture
输入: "数据库怎么连啊"          → How to create a database connection in watsonx
输入: "What is greedy decoding" → What is greedy decoding"""


class QueryRewriter:
    """使用配置的 LLM Provider 改写用户问题。"""

    def __init__(self, provider):
        self._client = provider.create_async_client()
        self._model = provider.model

    async def rewrite(self, question: str) -> str:
        """改写问题——中文→英文，口语→术语

        System 消息放 DOC_INDEX + 规则（始终相同 → 前缀缓存命中），
        User 消息只放问题本身。
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM.format(index=DOC_INDEX)},
                {"role": "user", "content": question},
            ],
            max_tokens=512,  # MiMo 内部消耗 token，需要充裕预算
        )

        rewritten = (response.choices[0].message.content or "").strip().strip('"').strip("'").strip()
        # MiMo 非思考模式偶发空返回 → 回退原问题，避免空查询污染全链路
        if not rewritten:
            return question
        return rewritten
