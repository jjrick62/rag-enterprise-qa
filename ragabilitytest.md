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

## 统计分析（2026-06-08）

对全部 10 组 RAGAS 评估（30 题×3 指标）做描述统计、效应量分析与 Judge 噪声量化。脚本：`backend/stats_analysis.py`。

### 描述统计

#### Faithfulness（忠实度）

| 配置 | 均值 | 标准差 | 最小 | 最大 | CV |
|------|:----:|:----:|:----:|:----:|:----:|
| **T02 ★生产** | **0.946** | **0.100** | 0.571 | 1.000 | **10.5%** |
| D4P-Frozen | 0.968 | 0.069 | 0.778 | 1.000 | 7.1% |
| T00 | 0.886 | 0.227 | 0.000 | 1.000 | 25.6% |
| T03 | 0.918 | 0.210 | 0.000 | 1.000 | 22.9% |
| Think | 0.927 | 0.155 | 0.333 | 1.000 | 16.7% |

T02 的变异系数（10.5%）在所有 MiMo 配置中最低——温度 0.2 不仅均值最高，答案质量也最稳定。

#### AnswerRelevancy（答案相关性）

| 配置 | 均值 | 标准差 | CV |
|------|:----:|:----:|:----:|
| T00 | 0.887 | 0.248 | 28.0% |
| **T02 ★** | **0.876** | 0.248 | 28.3% |
| T03 | 0.785 | 0.362 | 46.1% |

T03 的 CV 飙到 46.1%，温度 0.3 的答案已经开始失控。

### 效应量分析（Cohen's d）

#### D4P vs MiMo 严格对照

两组共享同一检索上下文、同一 Prompt、同一 Judge，仅替换生成模型（n=30 配对）。

| 指标 | D4P | MiMo T02 | 差值 | Cohen's d | 解读 |
|------|:----:|:----:|:----:|:----:|------|
| Faithfulness | 0.968 | 0.946 | +0.022 | +0.255 | 小效应 |
| AnswerRelevancy | 0.851 | 0.876 | -0.025 | -0.090 | 可忽略 |
| ContextPrecision | 0.831 | 0.869 | -0.039 | -0.134 | 可忽略 |

**三个指标没有一个达到中等效应量（|d|≥0.5）。** D4P 的忠实度优势仅为小效应（d=0.255），在 30 题的样本量下不具有统计显著性。选择 MiMo 的理由是综合成本、部署便利和已有额度，而不是质量碾压。

#### 温度效应（T02 为基准，逐题配对）

| 对比 | 指标 | 平均差异 | Cohen's d | 解读 |
|------|------|:----:|:----:|------|
| T02 vs T00 | Faithfulness | +0.059 | +0.340 | 小到中效应 |
| T02 vs T03 | AnswerRelevancy | +0.091 | +0.292 | 小效应 |
| T02 vs Think | Faithfulness | +0.018 | +0.120 | 可忽略 |

T02 对 T00 的优势方向一致但效应量不大——温度 0.2 确实优于 0.0，但不是一个碾压性的结论。思考模式（Think）与 T02 在所有维度上均无统计差异，但耗时更长。

#### 逐题胜负（以 T02 为基准，|diff|<0.02 记持平）

| 对比 | 指标 | T02 胜 | 持平 | 对手胜 |
|------|------|:--:|:--:|:--:|
| T02 vs T00 | Faithfulness | 9 | 13 | 8 |
| T02 vs T00 | **ContextPrecision** | 2 | **25** | 3 |
| T02 vs T03 | AnswerRelevancy | 10 | 13 | 7 |

**关键证据**：ContextPrecision 在 30 题中 25 题持平，验证了冻结上下文的实验设计有效性。剩余的 5 题差异全部来自 Judge 噪声。

### Judge 噪声量化

D4P-Frozen 和 MiMo T02 使用完全相同的检索上下文。理论上二者的 Context Precision 应完全一致。

实际结果：
- 均值差：-0.039
- 配对差异标准差：**SD = 0.250**

这意味着同一份上下文被同一个 Judge 评两次，Context Precision 就有 0.25 的标准差波动。Judge 噪声的大小排序：

```
Context Precision (SD=0.25) > AnswerRelevancy > Faithfulness (最稳定)
```

**推论**：
- **差值 < 0.05 的 RAGAS 分数不能作为决策依据**——它们很可能只是 Judge 的随机波动。
- Context Precision 的单次评测参考价值最弱，不应单独作为检索策略的评估标准。
- 需要重复评测（至少 2-3 次）才能对 0.03 级别的差异做结论。

### 过滤阈值单调性

| 阈值 | Faithfulness | AnsRelevancy | CtxPrecision | 三项均值 |
|:--:|:----:|:----:|:----:|:----:|
| off | 0.874 | 0.818 | 0.816 | 0.836 |
| 0.70 | 0.901 | 0.791 | 0.834 | 0.842 |
| **0.75** | **0.918** | **0.826** | **0.844** | **0.863** |
| 0.80 | 0.937 | 0.780 | 0.799 | 0.838 |

Faithfulness 随阈值单调递增，但 AnswerRelevancy 和 Context Precision 在 0.75 处同时达峰值。0.80 过滤过强，丢掉了有用上下文。

### 异常题诊断

跨 T00/T02/T03 三组取每题 Faithfulness 均值，识别系统性低分题：

| 题号 | 问题 | Faith 均值 | σ | 根因 |
|:--:|------|:--:|:--:|------|
| Q04 | random seed in prompt tuning? | 0.500 | 0.500 | 关键词歧义（prompt tuning vs 解码参数） |
| Q20 | IBM Db2 for z/OS versions? | 0.500 | 0.500 | 候选池深度不足，关键 chunk 靠后 |
| Q26 | NLP tasks in watsonx? | AnsRel=0.000 | — | 信息分散，单次检索难全覆盖 |
| Q09 | Why deploy prompt template? | CtxPrec=0.333 | 0.289 | 检索召回质量差 |

Q04 和 Q20 是系统性问题题——不管什么温度、什么模型，它们始终是 Faithfulness 最低的两个。这不是模型生成的问题，是**检索召回**的问题。

### 统计视角下的结论

1. **T02 选择得到统计支持**：Faithfulness 均值最高 + CV 最低 + 三项均值最高。
2. **但优势不是压倒性的**：T02 vs T00 的效应量仅为 d=0.34。诚实说法是「T02 优于 T00，但 30 题样本量下存在统计不确定性」。
3. **D4P vs MiMo 无法分出胜负**：三个指标的效应量均 < 0.3，两者在质量上近似等同。
4. **温度 0.3 明确不可用**：也是唯一一个效应量足够大、方向一致、规律明确的负面结果。
5. **Judge 噪声是当前评测体系最大的方法论限制**：需要重复评测或更大样本量才能做出高置信度的结论。

## 评测限制

- Answer Relevancy 请求 3 个 generations，但 MiMo 兼容接口只返回 1 个，因此存在额外波动。
- LLM Judge 并非确定性测量，**实测 Context Precision 的配对差异 SD = 0.25**，0.01～0.05 的小差异需要重复评测后才能作强结论。
- 当前 30 题适合项目迭代和面试展示，不等同于大规模统计显著性实验。若需要 p < 0.05 级别的结论，建议扩展到 100 题以上或对关键对比做 3 次重复评测取均值。

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
