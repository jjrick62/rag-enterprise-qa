# RAGAS 端到端能力评估报告

> 日期：2026-06-06
> 数据集：watsonxDocsQA 30 题
> 答案：DeepSeek V4 Pro 真实生成
> Judge：MiMo v2.5 Pro，thinking enabled
> 上下文：生成时实际使用的完整 chunk，无截断

## 当前正式结果

| 配置 | 平均上下文数 | Faithfulness | Answer Relevancy | Context Precision |
|---|---:|---:|---:|---:|
| 关闭相对过滤 | 5.00 | 0.874 | 0.818 | 0.816 |
| 0.70 | 4.47 | 0.901 | 0.791 | 0.834 |
| **0.75** | **4.10** | **0.918** | **0.826** | **0.844** |
| 0.80 | 3.83 | 0.937 | 0.780 | 0.799 |

当前选择 `0.75`：三项均超过目标线，综合均值最高。

## 指标目标

| 指标 | 当前 | 项目目标 | 状态 |
|---|---:|---:|---|
| Faithfulness | **0.918** | ≥0.80 | 达标 |
| Answer Relevancy | **0.826** | ≥0.70 | 达标 |
| Context Precision | **0.844** | ≥0.80 | 达标 |

## 关键修正

旧评测链路存在严重截断漏洞：

```text
生成模型：完整 chunk
旧 RAGAS：前端 excerpt，通常仅 200 字
```

答案依据经常位于 200 字之后，因此出现 Q00、Q02 等正确答案被判 `0.000`。修复后 RAGAS 直接使用生成时的完整 chunk，同时保留前端短摘要。

关闭过滤组在相同 Judge 下已达到 `0.874 / 0.818 / 0.816`，说明旧的低 Faithfulness 主要不是生成模型或 Prompt 本身造成的。

## 历史数据解释

- `0.864 / 0.897 / 0.911`：使用标准答案作为 response，适合观察检索是否支持标准答案，但不能代表端到端生成质量。
- `0.469 / 0.808 / 0.701` 等旧结果：评测上下文被压缩为短摘要，不应与当前结果直接比较。
- 当前四组是第一批“真实生成答案 + 完整生成上下文 + 固定 Judge”的正式可比基线。

## 已知波动

- 每组答案均为独立 LLM 调用，包含生成随机性。
- MiMo 对 Answer Relevancy 请求的 3 个 generations 实际只返回 1 个，单次结果可能波动。
- `0.75` 组 Q08、Q18 曾出现偶发拒答，需用固定上下文重复生成进一步判断。

## 产物

- 数据集：`data/evaluations/datasets/`
- 结构化报告：`data/evaluations/reports/ragas_*.json`
- 实验总结：`data/evaluations/reports/ragas_filter_experiment_2026-06-06.md`
- 历史日志：`data/evaluations/archive/`

## 结论

默认保留：

```text
min_score = 0.50
max_chunks_per_document = 4
adaptive_cutoff_ratio = 0.75
adaptive_keep_min = 3
```

下一轮不应继续盲调 Prompt，而应优先扩大候选召回深度并建立可重复的离线检索指标。
