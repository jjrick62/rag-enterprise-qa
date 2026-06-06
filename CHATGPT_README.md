# ChatGPT / Codex 工作记录

> 最后更新：2026-06-06
> 当前事实以根目录 `README.md`、`ragabilitytest.md` 和 `14.06claude写这里/README.md` 为准。

## 本轮完成

### 检索与摄入

- 修复 Hybrid BM25 分类过滤、RRF `top_k` 透传和启动时 BM25 重建。
- ChromaDB 全量重摄入改为 collection `clear()`，不删除活动数据库目录。
- 文档摄入补齐 404、删除失败中止和状态同步。
- RecursiveChunker 为 IBM 伪表增加确定性上下文，Q02 参数表可作为单个 chunk 检索。

### Reranker

当前默认：

```text
min_score = 0.50
max_chunks_per_document = 4
adaptive_cutoff_ratio = 0.75
adaptive_keep_min = 3
```

8 题离线基线：

| 阶段 | 平均答案覆盖率 | 覆盖率 ≥80% |
|---|---:|---:|
| Vector Top-5 | 70.5% | 5/8 |
| Hybrid/RRF Top-5 | 70.8% | 5/8 |
| Reranker Top-5 | **88.0%** | **7/8** |

### Prompt

- 从强制逐字引用调整为“允许忠实转述”。
- 明确表格和列表是有效证据。
- 有部分证据时只回答受支持部分。
- 仅在完全没有相关证据时拒答。
- 恢复文档冲突与问题歧义处理。

### RAGAS 截断漏洞

旧链路把生成模型看到的完整 chunk 转成前端 `Source.excerpt[:200]` 后再交给 RAGAS，导致 Judge 看不到答案依据。

当前修复：

- `GenerateEvent` 新增仅内部使用的 `contexts` 事件。
- Generator 发送生成时使用的完整 chunk。
- SSE 路由忽略内部事件，前端仍只收到 200 字摘要。
- `gen_answers.py` 保存完整答案和完整上下文。
- `RagasEvaluator` 移除答案 1500 字和上下文 500 字截断。
- `eval_ragas_only.py` 不再在缓存缺失时用标准答案伪造模型回答。

### 四组正式实验

四组共享同一次 Query Rewrite、召回和未启用相对过滤的 Top-5；只有过滤比例与后续答案生成不同。

| 相对阈值 | 平均上下文数 | Faithfulness | Answer Relevancy | Context Precision |
|---|---:|---:|---:|---:|
| 关闭 | 5.00 | 0.874 | 0.818 | 0.816 |
| 0.70 | 4.47 | 0.901 | 0.791 | 0.834 |
| **0.75** | **4.10** | **0.918** | **0.826** | **0.844** |
| 0.80 | 3.83 | 0.937 | 0.780 | 0.799 |

结论：默认采用 `0.75`。`0.80` 提升了 Faithfulness，但已经损害相关性和上下文精度。

## 评测注意事项

- Q00 和 Q02 在完整上下文下恢复为高分，证明旧 `0.000` 主要来自评测链路缺陷。
- Answer Relevancy 请求 3 个 generations，但当前 MiMo 兼容接口只返回 1 个，因此该指标有额外波动。
- 四组答案是独立 LLM 调用，不能把小幅差异全部归因于过滤策略。
- `0.864 / 0.897 / 0.911` 来自标准答案实验，不是端到端系统成绩。

## 文件位置

```text
data/evaluations/datasets/   四组答案、完整上下文和 legacy 数据
data/evaluations/reports/    四组 RAGAS JSON 和实验总结
data/evaluations/archive/    历史运行日志
```

## 模型与配置

| 角色 | 当前配置 |
|---|---|
| 在线服务生成 | DeepSeek Chat |
| 评测答案生成 | DeepSeek V4 Pro |
| RAGAS Judge | MiMo v2.5 Pro，thinking enabled |
| Query Rewrite | 在线服务仍使用 DeepSeek；实验脚本使用现有 QueryRewriter |

所有 API Key 已迁移至 `backend/.env`，代码中不得硬编码。

## 验证

```text
48 passed
```

## 下一步

1. 对候选池 `20 / 30 / 40 / 50` 做离线 Recall@5、MRR 和耗时实验。
2. 重点检查 Q08 正确 chunk 能否进入 Reranker。
3. 对 Q08、Q18 做固定上下文重复生成，区分检索问题和 LLM 随机拒答。
4. 再决定是否做 Parent-Child / 邻居 chunk。
