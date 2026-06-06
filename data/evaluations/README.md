# Evaluation Artifacts

## 目录

- `datasets/`：模型答案、ground truth、生成时完整上下文和实验标签。
- `reports/`：RAGAS 结构化 JSON 和实验总结。
- `archive/`：旧评测日志，仅用于追溯，不作为当前基线。

## 当前正式基线

`datasets/eval_dataset_r075.json` 对应：

```text
Faithfulness       0.918
Answer Relevancy   0.826
Context Precision  0.844
```

结构化结果位于 `reports/ragas_r075.json`。

## 命名

- `off`：关闭相对噪声过滤。
- `r070`：相对阈值 0.70。
- `r075`：相对阈值 0.75。
- `r080`：相对阈值 0.80。
- `legacy_truncated_contexts`：历史数据，不得用于当前结论。

禁止覆盖已有实验文件；新增实验应使用新的明确标签。
