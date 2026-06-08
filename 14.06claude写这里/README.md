# 当前交接入口

> 更新时间：2026-06-06 23:00 后  
> 这是 Claude、ChatGPT/Codex 和后续维护者应优先阅读的文件。

## 当前结论

- RAGAS 截断漏洞已修复。
- 当前生产推荐：MiMo T02，`0.946 / 0.876 / 0.869`，三项均值 `0.897`。
- D4P 冻结上下文严格对照：`0.968 / 0.851 / 0.831`，Faithfulness 单项最高。
- D4P 与 MiMo 仅看 Faithfulness + Answer Relevancy 时总体近似持平。
- 默认 Reranker 相对过滤比例：`0.75`。
- 非模型依赖回归：`68 passed`。
- API Key 已从代码迁移到 `backend/.env`。

## 阅读顺序

1. 根目录 `README.md`
2. 根目录 `ragabilitytest.md`
3. 本目录 `迭代记录_全量RAGAS分数.md`
4. 本目录 `RAG项目交接文档_2026-06-06.md`
5. 根目录 `CHATGPT_README.md`

## 文件状态

| 文件 | 状态 |
|---|---|
| `RAG项目交接文档_2026-06-06.md` | 当前交接，已更新 |
| `迭代记录_全量RAGAS分数.md` | 当前权威评分历史 |
| `ChatGPT交接_当前状态与纠结点_2026-06-06.md` | 已更新为问题闭环记录 |
| `项目文档与实现审计报告_2026-06-06.md` | 历史审计，问题多数已修复 |

## 下一任务

评分结论已经闭环。下一项检索优化仍是候选池深度实验：

```text
20 / 30 / 40 / 50 candidates
指标：Recall@5、MRR、答案覆盖率、Reranker 耗时
重点：Q08 repetitive text
```
