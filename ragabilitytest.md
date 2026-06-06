# RAGAS 端到端能力评估报告

> 日期：2026-06-07（更新）
> 数据集：watsonxDocsQA 30 题
> 答案：DeepSeek V4 Pro 真实生成
> Judge：MiMo v2.5 Pro，thinking enabled（订阅版 `token-plan-cn`）
> 上下文：生成时实际使用的完整 chunk，无截断
> Chunker：RecursiveChunker + IBM 纯文本标题 fallback（v2，1714 chunks）

## 当前正式结果（v2）

| 指标 | 分数 | 目标 | 状态 |
|------|:----:|:----:|:----:|
| Faithfulness | **0.931** | ≥0.80 | ✓ +0.131 |
| Answer Relevancy | **0.857** | ≥0.70 | ✓ +0.157 |
| Context Precision | **0.857** | ≥0.80 | ✓ +0.057 |

配置：RRF 20 → Reranker Top-5 → `min_score=0.50` + `max4/doc` + `adaptive_cutoff=0.75` + `keep_min=3`。

## 版本对比

| 版本 | Faith. | AnsRel. | CtxPrec. | Chunks | 说明 |
|------|:------:|:-------:|:--------:|:------:|------|
| F2（旧 chunker） | 0.918 | 0.826 | 0.844 | 1274 | heading 全部为空 |
| **v2（新 chunker）** | **0.931** | **0.857** | **0.857** | 1714 | heading 全量覆盖 |

**变更**：RecursiveChunker 新增 `_detect_ibm_headings()`——54 篇 IBM 文档全部无 `#` markdown 标题，旧版 `heading_stack` 全空。新版从首行提取标题、小节短行自动识别。Chunk 粒度更细（均值 285 vs 432 字符），语义边界更完整。

**结论**：三项反涨，IBM heading fallback 对检索质量正面。

## 性能对比

| 指标 | 旧 chunker | 新 chunker | 变化 |
|------|-----------|-----------|:----:|
| Chunk 总数 | 1274 | 1714 | +34.5% |
| 平均大小 | 432 chars | 285 chars | -34% |
| 空 heading | 全空（`[""]` bug） | 0/1714 | ✓ |
| 端到端延迟 | 2604ms | 2419ms | -7% |
| Reranker | 2558ms | 2384ms | -7% |

## 历史数据（存档）

| 配置 | Faith. | AnsRel. | CtxPrec. | 说明 |
|---|---|---|---|---|
| F0 关闭过滤 | 0.874 | 0.818 | 0.816 | 旧 chunker |
| F1 0.70 | 0.901 | 0.791 | 0.834 | 旧 chunker |
| F2 0.75 | 0.918 | 0.826 | 0.844 | 旧 chunker，上一基线 |
| F3 0.80 | 0.937 | 0.780 | 0.799 | 旧 chunker |

## 指标目标

| 指标 | 当前 v2 | 旧 F2 | 企业目标 |
|------|:------:|:------:|:------:|
| Faithfulness | **0.931** | 0.918 | ≥0.80 |
| Answer Relevancy | **0.857** | 0.826 | ≥0.70 |
| Context Precision | **0.857** | 0.844 | ≥0.80 |

## 产物

- 新数据集：`data/evaluations/datasets/eval_dataset_r075.json`
- 新报告：`data/evaluations/reports/ragas_r075_v2.json`
- 旧数据集/报告：`data/evaluations/archive/`
- 性能测试：`backend/perf_test.py`

## 结论

默认保留配置不变：
```text
min_score = 0.50
max_chunks_per_document = 4
adaptive_cutoff_ratio = 0.75
keep_min = 3
```

IBM 标题 fallback 已验证有效，chunk 语义边界改善带来三项指标全面提升。
