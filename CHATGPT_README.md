# ChatGPT 工作记录与交接

> 更新日期：2026-06-06  
> 作用：仅记录 ChatGPT/Codex 在本项目完成的修改、验证结果和后续注意事项。  
> 总体项目说明仍以根目录 `README.md` 和 Claude 的交接文档为准。

## 一、本轮已完成

### 1. Hybrid 检索与索引安全

- BM25 检索现在支持 `category_filter`，与向量检索过滤行为一致。
- `HybridRetriever.search(top_k=...)` 现在遵守调用方要求：
  - 双路候选池至少保留 20 条。
  - 最终 RRF 返回数量使用调用方的 `top_k`，不再固定为 15。
- ChromaDB 启动重建 BM25 失败时会输出 warning，不再静默退化。
- 为 Retriever 增加 `clear()` 接口。
- 全量重摄入通过 collection API 清空数据，不再删除正在使用的 ChromaDB 目录。
- `_reingest.py` 同样改用 `clear()`，避免数据库锁和目录损坏风险。

### 2. 文档摄入接口

- 不存在的文件会在初始化 Pipeline 前返回 HTTP 404。
- 强制更新已有文档时，如果旧向量删除失败，会返回 HTTP 500 并停止摄入。
- 删除失败不再被吞掉，避免新旧向量同时存在。

### 3. Chunk 上下文增强

- 表格 chunk 增加确定性上下文前缀：
  - `Document`
  - `Category`
  - `Table context`
- 普通文本 chunk 保持原样。
- 没有使用 LLM 预处理所有 chunk，也没有增加 LLM fallback。
- 重建后的索引包含 54 篇文档、637 个 chunk。
- Q02 “What tuning parameters are available for IBM foundation models?” 在离线 BM25 和 Hybrid/RRF 检索中均提升到第 1 名。

### 4. 评估和诊断脚本

- 修复 `ablation_test.py` 被 pytest 误收集的问题。
- `gen_answers.py` 和 `run_ragas_eval.py` 不再隐藏截断到前 20 条，按实际数据集数量运行。
- `_trace_q02.py` 已适配当前：
  - `build_context_block(List[RetrievalResult])`
  - `DeepSeekGenerator.generate()` 异步事件流
- 增加静态回归测试，防止评估脚本重新出现 `qa_pairs[:20]`。

## 二、RAGAS 费用警告

当前 RAGAS Judge 配置位于：

```text
backend/services/ragas_evaluator.py
```

使用模型：

```text
deepseek-chat
```

该兼容别名当前对应 `deepseek-v4-flash` 的非思考模式，不是 Pro。

当前启用三个指标：

- Faithfulness：每题通常需要 2 次 LLM 调用。
- Answer Relevancy：每题请求生成 3 个候选问题。
- Context Precision：对每个检索 context 单独调用 LLM；当前每题通常有 5 个 context。

因此一次 20 题评估的实际 API 请求量远高于进度条显示的 60 个指标任务，估算约 160 次；再加答案生成和 Query Rewrite，整轮约 200 次。重复运行 3 至 4 次可能产生约 600 至 800 次请求。

RAGAS 各题的 question、answer、ground truth 和 context 不同，DeepSeek 的前缀缓存难以大量复用，所以出现约 90% 缓存未命中是合理现象。

### 当前约束

- 暂不运行 `backend/eval_ragas_only.py`。
- 暂不运行 `backend/run_ragas_eval.py`。
- 未经明确确认，不进行完整 30 题 RAGAS 评估。
- 普通代码测试 `pytest` 不调用 DeepSeek API，可以正常运行。

## 三、Embedding 候选模型

现有模型与索引完整保留：

```text
模型：BAAI/bge-small-zh-v1.5
维度：512
索引：data/chroma_db
```

已新增并下载英文候选模型：

```text
模型：BAAI/bge-base-en-v1.5
维度：768
缓存：backend/models
快照：a5beb1e3e68b9ab74eb54cfd186867f64f240e1a
```

离线加载验证：

```text
shape=(1, 768)
dtype=float32
```

新增配置：

```dotenv
ENGLISH_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
ENGLISH_CHROMA_PATH=../data/chroma_db_bge_base_en
```

默认服务配置没有切换，仍使用：

```dotenv
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
CHROMA_PATH=../data/chroma_db
```

注意：512 维与 768 维向量不能写入同一个 Chroma collection。英文模型必须使用独立索引目录。

## 四、测试状态

从 `backend` 目录运行：

```powershell
.\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests ablation_test.py
```

当前完整回归结果：

```text
40 passed
```

英文模型已完成真实离线加载和单条 embedding 验证。

## 五、当前中文 Embedding 离线检索基线

测试条件：

```text
模型：BAAI/bge-small-zh-v1.5
索引：637 chunks
问题：8 道代表题
Query Rewrite：关闭
LLM / API：未调用
指标：Top-5 检索文本对标准答案非停用词的覆盖率
```

结果：

| 阶段 | 平均覆盖率 | 覆盖率 ≥50% | 覆盖率 ≥80% |
|------|-----------:|------------:|------------:|
| Vector Top-5 | 70.5% | 6/8 | 5/8 |
| Hybrid/RRF Top-5 | 70.8% | 6/8 | 5/8 |
| Reranker Top-5 | **88.0%** | **7/8** | **7/8** |

代表题：

- Q01 foundation models：Reranker Top-5 覆盖率 100%。
- Q03 tuning parameters：覆盖率 86.7%，六项参数完整存在同一个表格 chunk。
- Q14 RAG pattern：Hybrid 将覆盖率从 62.1% 提升至 89.7%。
- Q18 ontology：Vector Top-5 为 0%，Reranker 提升至 93.8%。
- Q19 geospatial library：Reranker 将 Hybrid 的 64.3% 提升至 95.2%。
- Q08 repetitive text：Reranker Top-5 仅 38.5%，是当前明确弱项。

Q08 正确的 `repetition penalty` chunk 排名：

```text
Vector Top-50：22
BM25 Top-50：34
RRF Top-50：18
进入 Reranker 后：1
```

当前 Pipeline 只给 Reranker 20 个候选，而且 Vector 与 BM25 各自只召回 20。该正确 chunk 因此未进入当前精排链路。这个结果说明 Reranker 本身有效，Q08 的主要瓶颈位于候选召回深度。

## 六、Reranker 阈值与多样性实验

### 阈值实验

固定当前 20 个候选，对 `0.50 / 0.55 / 0.60 / 0.65` 进行离线对比：

| 最低分数 | 平均答案覆盖率 | 平均保留数 | 覆盖率 ≥80% |
|---------:|---------------:|-----------:|------------:|
| **0.50** | **88.0%** | 5.00 | **7/8** |
| 0.55 | 80.4% | 2.88 | 6/8 |
| 0.60 | 80.4% | 2.50 | 6/8 |
| 0.65 | 78.7% | 2.12 | 6/8 |

结论：

- 默认 `min_score=0.50`。
- 更高阈值会明显损失标准答案覆盖率。
- 如果全部候选低于阈值，保留最高分 1 条，避免生成上下文完全为空。

### Top-5 多样性实验

比较同一文档最多保留 2、3、4 条 chunk：

| 每文档上限 | 平均答案覆盖率 | 平均来源文档数 | 覆盖率 ≥80% |
|-----------:|---------------:|---------------:|------------:|
| 2 | 82.9% | 3.50 | 6/8 |
| 3 | 83.8% | 2.88 | 6/8 |
| **4** | **88.0%** | **2.38** | **7/8** |
| 不限制 | 88.0% | 1.88 | 7/8 |

硬限制为 2 会让 Q19 从 95.2% 降到 61.9%，因为同一正确文档中的互补 chunk 被删掉。最终采用温和策略：

```text
min_score = 0.50
max_chunks_per_document = 4
```

该策略保持 88.0% 平均覆盖率，同时将 Top-5 平均来源文档数从 1.88 提升到 2.38。

实现位置：

```text
backend/services/reranker.py
```

行为：

- 过滤分数低于 0.50 的明确负相关候选。
- Top-5 中同一文档最多占 4 条。
- 不用低分结果强行补满 Top-5。
- 全部低于阈值时仅保留最高分结果。
- 构造参数可覆盖，便于后续继续实验。

## 七、建议的下一步

1. 不调用 LLM，建立 30 题检索基线：Recall@5、MRR、目标文档排名。
2. 使用独立英文索引目录构建 `bge-base-en-v1.5` 索引。
3. 在相同 chunk、BM25、RRF 和 reranker 配置下，对比中文模型与英文模型。
4. 重点检查 Q02、Q07、Q13、Q15、Q17、Q18。
5. 确认英文模型确实提升后，再决定是否修改默认 `.env`。
6. 最后才考虑运行一次受控的小样本 RAGAS，完整评估必须先预估费用并得到确认。

## 八、优化路线决策记录

> 用户给出的优化方向（按优先级排序，2026-06-06 15:37）：

| 优先级 | 方向 | 当前状态 |
|--------|------|---------|
| 1 | Reranker 阈值过滤 | ✅ 已完成 |
| 2 | Top-5 多样性控制 | ✅ 已完成 |
| 3 | Parent-Child / 邻居 Chunk | 待做 |
| 4 | Query Rewrite 优化（减少 API 调用） | 待做 |
| 5 | 检索置信度与拒答 | 待做 |
| 6 | Graph RAG | 远期 |
| — | Embedding 切换（中→英） | 已下载模型，暂不切换 |

### 实验设计决策

1. **先跑本地基线，再动手改**：不直接调参，先用 8 道代表题 + 标准答案覆盖率建立离线基线，拿到数据后再决定方向。
2. **一次只改一个变量**：阈值实验和多样性实验虽然同时改代码，但离线评估时分别对比——阈值实验固定无多样性限制，多样性实验固定阈值 0.50。候选池保持 20，不跟候选扩展混在一起。
3. **不直接拍脑袋固定阈值**：离线比较 0.50 / 0.55 / 0.60 / 0.65 四个档位，看覆盖率变化再定默认值。
4. **多样性用温和策略**：上限 2 会把 Q19 覆盖率从 95.2% 砍到 61.9%（同一文档的互补 chunk 被删掉），最终选上限 4。

### 工作流程

```
用户: "先跑几个基本测试，和标准答案对照，拿到数据"
  → ChatGPT 跑 8 题离线基线，全程本地不调 API
  → 输出 Vector/Hybrid/Reranker 三级覆盖率

用户: "更新 gptreadme，然后按优化方向 1+2 做"
  → ChatGPT 提方案设计（阈值离线对比、多样性温和策略）
  → 用户确认 "干活"
  → 实现 + 实验 + 更新文档
  → 40 passed
```

## 九、工作区提醒

当前工作区包含 Claude、用户实验脚本、评估输出和 ChatGPT 的修改，尚未统一提交。不要使用 `git reset --hard` 或批量覆盖文件。合并或提交前应按文件确认改动归属。
