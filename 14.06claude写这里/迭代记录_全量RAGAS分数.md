# RAGAS 评分迭代记录

> 数据集：watsonxDocsQA 30 题  
> 日期：2026-06-06  
> 当前权威结果以“真实生成答案 + 完整生成上下文 + MiMo Judge”为准。

## 全部历史

| 轮次 | 生成 | Judge | Faith. | AnsRel. | CtxPrec. | 有效性 | 说明 |
|---|---|---|---:|---:|---:|---|---|
| L0 | DeepSeek 中文 | DeepSeek | 0.566 | 0.672 | 0.560 | 历史 | 早期基线 |
| L1 | DeepSeek 英文 | DeepSeek | 0.610 | 0.770 | 0.550 | 历史 | Prompt 英文化 |
| L2 | DeepSeek | MiMo 关 thinking | 0.544 | 0.753 | 0.865 | 历史 | 不同 Judge，不可横比 |
| L3 | DeepSeek | MiMo 开 thinking | 0.540 | 0.762 | 0.614 | 历史 | 不同 Judge，不可横比 |
| GT | 标准答案 | MiMo 开 thinking | 0.864 | 0.897 | 0.911 | 非端到端 | response 不是模型答案 |
| L4 | DeepSeek | MiMo 开 thinking | 0.498 | 0.784 | 0.730 | 截断污染 | RAGAS 上下文不完整 |
| L5 | MiMo | MiMo 开 thinking | 0.451 | 0.791 | 0.721 | 截断污染 | 同上 |
| L6 | DeepSeek V4 Pro | MiMo 开 thinking | 0.469 | 0.808 | 0.701 | 截断污染 | 严格 Prompt、自适应过滤 |
| **F0** | **DeepSeek V4 Pro** | **MiMo 开 thinking** | **0.874** | **0.818** | **0.816** | **正式** | 完整上下文，关闭相对过滤 |
| **F1** | **DeepSeek V4 Pro** | **MiMo 开 thinking** | **0.901** | **0.791** | **0.834** | **正式** | 相对阈值 0.70 |
| **F2** | **DeepSeek V4 Pro** | **MiMo 开 thinking** | **0.918** | **0.826** | **0.844** | **当前基线** | 相对阈值 0.75 |
| **F3** | **DeepSeek V4 Pro** | **MiMo 开 thinking** | **0.937** | **0.780** | **0.799** | **正式** | 相对阈值 0.80 |

## 为什么旧分数失效

旧 `gen_answers.py` 从 `sources` 事件读取 `Source.excerpt`。该字段专为前端设计，长度最多 200 字。RAGAS 因此审查的是残缺上下文，而生成模型使用的是完整 chunk。

典型影响：

- Q00 模型列表：答案与原文一致，旧评测仍可能为 0。
- Q02 调参表：参数值位于完整表格中，短摘要无法稳定覆盖。
- 删除 deployment、Db2 版本、Box 类型等题目的关键句位于截断点之后。

因此 L4-L6 只能作为“发现异常的历史记录”，不能用于判断模型、Prompt 或 Reranker 的真实质量。

## F0-F3 实验控制

每道题：

1. Query Rewrite 一次。
2. Vector + BM25 召回一次。
3. Reranker 在关闭相对过滤时生成共同 Top-5。
4. 对共同 Top-5 分别应用 off、0.70、0.75、0.80。
5. 每组独立生成答案。
6. 保存各组真实完整上下文。

## 选择 0.75

| 比例 | 三项均值 | 判断 |
|---|---:|---|
| off | 0.836 | 上下文较多 |
| 0.70 | 0.842 | Precision 提升，但 Relevancy 波动 |
| **0.75** | **0.863** | 综合最优 |
| 0.80 | 0.839 | Faithfulness 高，但过滤过强 |

## 文件

```text
data/evaluations/datasets/eval_dataset_*.json
data/evaluations/reports/ragas_*.json
data/evaluations/reports/ragas_filter_experiment_2026-06-06.md
data/evaluations/archive/
```

## 当前测试

`48 passed`
