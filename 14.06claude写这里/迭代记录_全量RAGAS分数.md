# RAGAS 评分迭代记录

> 数据集：watsonxDocsQA 30 题
> 日期：2026-06-06
> 当前权威结果以“真实生成答案 + 完整生成上下文 + MiMo Judge”为准。
> 当前生产推荐：MiMo T02（0.946 / 0.876 / 0.869）。
> 单项最高 Faithfulness：D4P Frozen（0.968）。

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
| **F2** | **DeepSeek V4 Pro** | **MiMo 开 thinking** | **0.918** | **0.826** | **0.844** | **历史正式** | 相对阈值 0.75 |
| **F3** | **DeepSeek V4 Pro** | **MiMo 开 thinking** | **0.937** | **0.780** | **0.799** | **正式** | 相对阈值 0.80 |
| **v2** | **DeepSeek V4 Pro** | **MiMo 订阅版** | **0.931** | **0.857** | **0.857** | **历史基线** | IBM 标题 fallback，1714 chunks，0.75 |
| T00 | MiMo v2.5 Pro，temp=0.0 | MiMo 开 thinking | 0.886 | **0.887** | **0.881** | 正式 | 冻结上下文温度实验 |
| **T02** | **MiMo v2.5 Pro，temp=0.2** | **MiMo 开 thinking** | **0.946** | **0.876** | **0.869** | **当前生产推荐** | 冻结上下文，三项均值 0.897 |
| T03 | MiMo v2.5 Pro，temp=0.3 | MiMo 开 thinking | 0.918 | 0.785 | 0.875 | 正式 | 相关性明显下降 |
| Think | MiMo v2.5 Pro，思考模式 | MiMo 开 thinking | 0.927 | 0.844 | 0.836 | 正式 | 更慢且未超过 T02 |
| **D4P-Frozen** | **DeepSeek V4 Pro，temp=0.2，非思考** | **MiMo 开 thinking** | **0.968** | **0.851** | **0.831** | **严格对照** | 与 T02 共用同一冻结上下文和 Prompt |

## 2026-06-07 MiMo 温度实验

| 组别 | 三项均值 | 结论 |
|---|---:|---|
| T00 | 0.885 | 相关性与上下文精度略高，但 Faithfulness 较低 |
| **T02** | **0.897** | **综合最优，作为生产配置** |
| T03 | 0.859 | Answer Relevancy 降至 0.785 |
| Think | 0.869 | 成本与耗时更高，没有质量收益 |

## 2026-06-07 D4P 严格对照

T02 与 D4P-Frozen 使用同一份 `contexts_r075.json`、同一 Prompt、同一温度 0.2 和同一 MiMo Judge，仅替换生成模型。

| 模型 | Faith. | AnsRel. | CtxPrec. | 三项均值 |
|---|---:|---:|---:|---:|
| D4P | **0.968** | 0.851 | 0.831 | 0.883 |
| **MiMo T02** | 0.946 | **0.876** | **0.869** | **0.897** |

- D4P 忠实度更高、回答更短。
- MiMo 相关性和综合均值更高。
- Context Precision 在相同上下文下仍波动 0.038，说明 Judge 存在噪声。
- 只看 Faithfulness 与 Answer Relevancy，两者均值分别为 0.910 和 0.911，整体近似持平。

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

`68 passed`（排除依赖本地模型缓存的 embedder 测试）

## 2026-06-07 Chunker 变更（IBM 纯文本标题 fallback）

**问题**：IBM watsonx 54 篇文档无一使用 Markdown `#` 标题，全部为纯文本格式。旧 chunker 的 `_parse_heading_tree` 正则 `^(#{1,6})\s+(.+)$` 匹配不到任何内容 → 所有 chunk 的 `heading_stack=[]` → 前端引用卡片全显示 `(no heading)`。

**修复**：`RecursiveChunker` 新增 `_detect_ibm_headings()` fallback 方法：无 Markdown 标题时自动从文档首行提取标题、根据段落间距和句子特征识别小节标题。排除列表项、表格标题、伪表数据行等误判。

**影响**：
- Chunk 总数从 ~660 增至 876（小节拆分更细）
- 表块更独立（表周围不再跟前后段混一块）
- Chunk 边界全局变化 → 必须重摄入 + 重评估

**IBM 标题 fallback 评估**（2026-06-07 已完成，现为历史基线）：
- 重摄入 54 篇文档 → 1714 chunks
- 生成 1 组答案（0.75）
- MiMo 订阅版 Judge 评估 → Faith 0.931 / AnsRel 0.857 / CtxPrec 0.857
- 该结果随后被 MiMo T02 当前生产分数 0.946 / 0.876 / 0.869 超越
- D4P-Frozen 严格对照为 0.968 / 0.851 / 0.831
