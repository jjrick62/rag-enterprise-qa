# RAGAS 自适应过滤对比实验

日期：2026-06-06

## 实验设计

- 30 道 watsonxDocsQA 测试题。
- 每道题只执行一次 Query Rewrite、召回和 Reranker，得到共同 Top-5。
- 分别应用关闭过滤、0.70、0.75、0.80 四种相对阈值。
- 每组独立生成答案，保存生成时实际使用的完整 chunk。
- RAGAS 不截断答案或上下文，Judge 使用 MiMo v2.5 Pro。

## 结果

| 相对阈值 | 平均上下文数 | Faithfulness | Answer Relevancy | Context Precision | 三项均值 |
|---|---:|---:|---:|---:|---:|
| 关闭 | 5.00 | 0.874 | 0.818 | 0.816 | 0.836 |
| 0.70 | 4.47 | 0.901 | 0.791 | 0.834 | 0.842 |
| **0.75** | **4.10** | **0.918** | **0.826** | **0.844** | **0.863** |
| 0.80 | 3.83 | 0.937 | 0.780 | 0.799 | 0.839 |

## 结论

- 默认保留 `adaptive_cutoff_ratio=0.75`。
- 0.75 同时提高了三项指标，是本轮最均衡方案。
- 0.80 虽然进一步提高 Faithfulness，但 Answer Relevancy 和 Context Precision 明显下降，过滤已经过强。
- 修复完整上下文评测后，关闭过滤组的 Faithfulness 已从旧记录约 0.47 恢复到 0.874，说明此前低分主要来自评测截断漏洞。
- Q00 模型列表和 Q02 调参参数在完整上下文下均能正确回答并获得高 Faithfulness，不能再用旧分数判断 Prompt 或检索质量。

## 注意事项

- 四组答案是独立 LLM 调用，仍包含少量生成随机性。
- 0.75 组在 Q08 和 Q18 出现偶发拒答，但相邻组能够回答，需要后续做固定样本重复生成测试。
- RAGAS Answer Relevancy 请求 3 个 generations 时，MiMo 实际仅返回 1 个，日志持续出现相应警告。因此 Answer Relevancy 的单次结果存在额外波动。

## 产物

- `../datasets/eval_dataset_off.json`
- `../datasets/eval_dataset_r070.json`
- `../datasets/eval_dataset_r075.json`
- `../datasets/eval_dataset_r080.json`
- `ragas_off.json`
- `ragas_r070.json`
- `ragas_r075.json`
- `ragas_r080.json`
