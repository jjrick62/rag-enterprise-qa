# RAG 系统能力评估报告 (RAGAS)

> **框架**: RAGAS 0.4.3 | **LLM Judge**: DeepSeek Chat | **测试集**: watsonxDocsQA (20条)
> **被测管线**: RecursiveChunker + Hybrid(BM25+Vector+RRF) + BGE-Reranker-v2-m3 + QueryRewriter + DeepSeek

---

## 一、评估方法

RAGAS 三个核心指标：

| 指标 | 方法 | 测什么 |
|------|------|--------|
| Faithfulness | 两步法（拆claims→逐条核验） | 回答中有多少是文档里能找到的 |
| Answer Relevancy | embedding语义相似度 + LLM反向生成 | 回答是否直接回应了问题 |
| Context Precision | LLM逐段判断相关性 | 检索回来的文档跟问题沾不沾边 |

---

## 二、两轮评估对比

### Round 1: 七段结构 Prompt（1498字）

| 指标 | 分数 | vs企业标准 |
|------|------|-----------|
| Faithfulness | **0.575** | -0.225 |
| Answer Relevancy | **0.714** | ✅ |
| Context Precision | **0.487** | -0.313 |

**问题**: Prompt 要求五段输出（结论摘要→制度依据→关键提示→引用清单→关联线索），LLM 为了填满"关键提示"和"关联线索"编造内容。

### Round 2: 简化 Prompt（450字，去除强制结构）

| 指标 | 分数 | vs企业标准 | vs Round 1 |
|------|------|-----------|-----------|
| Faithfulness | **0.542** | -0.258 | -0.033 |
| Answer Relevancy | **0.588** | -0.112 | -0.126 |
| Context Precision | **0.537** | -0.263 | **+0.050** |

**分析**: 
- Faithfulness 微跌 0.033 —— 简化 Prompt 后 LLM 更诚实了（12字拒答 vs 编造1500字），但拒答被 RAGAS 判 0 分。**这是指标的局限，不是模型的退步。**
- Answer Relevancy 跌 0.126 —— 同理，拒答跟问题不匹配。
- Context Precision +0.050 —— 检索质量本身有微弱提升（可能是 Prompt 改变后 Query 改写行为也跟着变了）。

**关键结论**: 仅靠改 Prompt 不够。根因在检索——Context Precision=0.53，一半的检索结果跟问题不沾边。LLM 拿到垃圾上下文，要么拒答（Faithfulness 无法评估），要么硬编（Faithfulness 低）。**必须先修检索。**

---

## 三、问题诊断

### 问题一：检索精度不足（Context Precision=0.53）

54篇 IBM 文档集中在 Decision Optimization 和 Foundation Models。跨领域查询时（如 ontology、CLEM、SPSS Modeler），BM25+向量找不到精确匹配，只能返回"语义接近但不相关"的文档。

### 问题二：Reranker 没有做阈值过滤

当前所有检索结果都送 LLM，即使 Reranker 分低至 0.50。低分 chunk 注入的噪声比价值大。

### 问题三：RAGAS Faithfulness 对拒答评分不友好

12 字的"参考文档中未包含该信息"被拆成 0 条 claims → Faithfulness=0。诚实回答被指标惩罚，这是一个已知的 RAGAS 局限性。

---

## 四、优化路线（更新后）

### P0：检索精度——Context Precision 0.53 → 0.70

| 措施 | 预期提升 | 状态 |
|------|---------|------|
| 简化 System Prompt | Context Precision +0.05 | ✅ 已完成 |
| Reranker 阈值过滤（score<0.5 不送 LLM） | +0.10 | 🔜 |
| 知识库扩展：补充缺失领域文档 | +0.07 | 🔜 |
| Query 改写 Prompt 优化（跨领域术语映射） | +0.05 | 🔜 |

### P1：RAGAS 评估完善

| 措施 | 说明 |
|------|------|
| Answer Relevancy 修复 | 当前用本地 BGE 512 维，需验证跟 RAGAS 默认 OpenAI 1536 维的可比性 |
| 拒答场景专项评估 | RAGAS 对拒答不友好，需补充人工评估 |

### P2：长期

| 措施 | 说明 |
|------|------|
| Graph RAG | 知识图谱增强检索（Q3.1 炫技目标，后置） |
| 多轮对话完善 | 会话管理已实现，前端未做 |

---

## 五、评估工具链

```bash
# Step 1: 生成回答（换 Prompt/参数后重跑）
venv_ragas\Scripts\activate
python backend/gen_answers.py

# Step 2: RAGAS 评估（从缓存 JSON 读回答，秒级重跑）
python backend/eval_ragas_only.py
```
