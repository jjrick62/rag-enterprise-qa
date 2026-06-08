# RAGAS 端到端能力评估报告

> 更新日期：2026-06-07
> 数据集：watsonxDocsQA 30 题
> 当前生产生成：MiMo v2.5 Pro，非思考模式，temperature=0.2
> Judge：MiMo v2.5 Pro，thinking enabled
> 上下文：生成时实际使用的完整 chunk，无截断
> 检索：RRF Top-20 → BGE Reranker Top-5 → 0.50 绝对阈值 → 0.75 相对阈值 → 至少 3 条

## 当前生产推荐：MiMo T02

| 指标 | 分数 | 目标 | 状态 |
|---|---:|---:|---|
| Faithfulness | **0.946** | ≥0.80 | +0.146 |
| Answer Relevancy | **0.876** | ≥0.70 | +0.176 |
| Context Precision | **0.869** | ≥0.80 | +0.069 |
| 三项均值 | **0.897** | — | 当前最高综合均值 |

选择理由：

- 四组 MiMo 生成实验中，T02 的 Faithfulness 与三项均值最高。
- T00 的 Answer Relevancy 和 Context Precision 略高，但 Faithfulness 低 0.060。
- T03 的 Answer Relevancy 降至 0.785。
- Thinking 模式更慢，三项均值仅 0.869，没有超过非思考 T02。

## MiMo 温度与模式实验

四组使用同一次冻结检索上下文，只改变答案生成温度或思考模式。

| 组别 | 生成模式 | Faith. | AnsRel. | CtxPrec. | 三项均值 | RAGAS 耗时 |
|---|---|---:|---:|---:|---:|---:|
| T00 | temperature=0.0 | 0.886 | **0.887** | **0.881** | 0.885 | 24.5 min |
| **T02** | **temperature=0.2** | **0.946** | 0.876 | 0.869 | **0.897** | 24.3 min |
| T03 | temperature=0.3 | 0.918 | 0.785 | 0.875 | 0.859 | 26.8 min |
| Thinking | reasoning enabled | 0.927 | 0.844 | 0.836 | 0.869 | 26.4 min |

结论：生产生成采用 MiMo v2.5 Pro 非思考模式，`temperature=0.2`。

## D4P 与 MiMo 严格单变量对照

两组共享：

- 同一份 `contexts_r075.json`
- 同一套 Prompt
- 同一温度 `0.2`
- 同一个 MiMo Judge
- 同一批 30 道题

唯一变量是答案生成模型。

| 生成模型 | Faith. | AnsRel. | CtxPrec. | 三项均值 | 平均回答长度 |
|---|---:|---:|---:|---:|---:|
| DeepSeek V4 Pro | **0.968** | 0.851 | 0.831 | 0.883 | 505 chars |
| **MiMo v2.5 Pro T02** | 0.946 | **0.876** | **0.869** | **0.897** | 596 chars |

逐题对比（差值小于 0.02 记为持平）：

| 指标 | D4P 胜 | MiMo 胜 | 持平 |
|---|---:|---:|---:|
| Faithfulness | 8 | 5 | 17 |
| Answer Relevancy | 8 | 7 | 15 |
| Context Precision | 3 | 4 | 23 |

解释：

- D4P 的 Faithfulness 高 0.022，回答更短，适合强调极致防编造的场景。
- MiMo 的 Answer Relevancy 高 0.025，生产综合均值高 0.014。
- Context Precision 理论上主要由冻结检索上下文决定。本次同上下文仍出现 0.038 差异，说明单次 LLM Judge 存在波动，不应将其完全归因于生成模型。
- 仅平均 Faithfulness 与 Answer Relevancy：D4P=0.910，MiMo=0.911，实际近似持平。
- 当前继续选择 MiMo T02，原因是综合质量、现有部署和额度成本更合适；D4P 保留为高 Faithfulness 对照。

## 历史基线

| 版本 | 生成模型 | Faith. | AnsRel. | CtxPrec. | 说明 |
|---|---|---:|---:|---:|---|
| F2 | D4P | 0.918 | 0.826 | 0.844 | 旧 chunker，阈值 0.75 |
| v2 | D4P | 0.931 | 0.857 | 0.857 | IBM 标题 fallback |
| **MiMo T02** | **MiMo** | **0.946** | **0.876** | **0.869** | **当前生产推荐** |
| D4P Frozen | D4P | **0.968** | 0.851 | 0.831 | 同上下文生成模型对照 |

旧 L4-L6 使用了被截断为前端 200 字摘要的上下文，属于评测污染，只保留为故障历史，不能用于模型质量结论。

## 评测限制

- Answer Relevancy 请求 3 个 generations，但 MiMo 兼容接口只返回 1 个，因此存在额外波动。
- LLM Judge 并非确定性测量，0.01～0.04 的小差异需要重复评测后才能作强结论。
- 当前 30 题适合项目迭代和面试展示，不等同于大规模统计显著性实验。

## 产物

```text
data/evaluations/datasets/contexts_r075.json
data/evaluations/datasets/eval_dataset_r075_t00.json
data/evaluations/datasets/eval_dataset_r075_t02.json
data/evaluations/datasets/eval_dataset_r075_t03.json
data/evaluations/datasets/eval_dataset_r075_think.json
data/evaluations/datasets/eval_dataset_r075_d4p_t02.json

data/evaluations/reports/ragas_t00.json
data/evaluations/reports/ragas_t02.json
data/evaluations/reports/ragas_t03.json
data/evaluations/reports/ragas_think.json
data/evaluations/reports/ragas_d4p_frozen_t02.json
```

## 最终决策

```text
generation_model = MiMo v2.5 Pro
thinking = disabled
temperature = 0.2
min_score = 0.50
max_chunks_per_document = 4
adaptive_cutoff_ratio = 0.75
keep_min = 3
```
