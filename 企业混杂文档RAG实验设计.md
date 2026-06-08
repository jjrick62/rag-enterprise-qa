# 企业混杂文档 RAG 实验设计

> 版本：v1.0
> 日期：2026-06-08
> 目标：构建一个公开可复现、接近企业内部知识库形态的混杂文档基准，验证 RAG 系统在噪声、近重复、版本冲突和无答案场景下的稳定性。
> 原则：服务简历展示与面试讲解，优先追求高信息密度和可解释结论，不追求超大规模。

## 1. 实验价值

当前 watsonxDocsQA 主要验证同领域技术文档问答能力，但真实企业知识库通常还包含：

- 多部门文档混合；
- 中英文内容并存；
- 正式制度、FAQ、会议纪要和操作手册同时存在；
- 同一制度的新旧版本并存；
- 模板、重复内容和高相似文档；
- 文档中不存在答案的问题。

本实验用于回答：

1. 无关和高相似文档增加后，检索质量下降多少？
2. 系统能否优先选择当前有效版本，而不是旧版制度？
3. 面对会议纪要与正式制度的不同口径，系统能否识别文档权威性？
4. 面对知识库中不存在的信息，系统能否正确拒答？
5. 中英文混合语料是否影响中文问题的检索与回答？

## 2. 范围与成本

采用高收益精简方案：

| 项目 | 规模 |
|---|---:|
| 原始公开资料 | 约 30 篇 |
| 整理后的企业文档 | 约 45 份 |
| 人工审核 QA | 30 题 |
| 压力等级 | 3 组 |
| 生产生成配置 | MiMo v2.5 Pro，非思考，temperature=0.2 |
| Judge | MiMo v2.5 Pro，thinking enabled |

预计投入：

- 资料选择与整理：2–3 小时；
- 旧版、重复和冲突文档构造：1–2 小时；
- QA 生成与人工审核：2–4 小时；
- 建库、运行和分析：2–3 小时。

总计约 1 个工作日。若首轮无法形成清晰结论，不扩大到 100 份文档或 60 道题。

## 3. 公开资料来源

优先选择官方、可公开访问并允许合理引用的资料：

| 来源 | 主要内容 | 用途 |
|---|---|---|
| GitLab Handbook | HR、安全、差旅、采购、工程和管理流程 | 企业制度主体 |
| GitHub Docs / Site Policy | 权限、安全、合规和研发流程 | 技术与合规资料 |
| Atlassian Team Playbook | 项目启动、会议、复盘、协作和变更管理 | 项目管理资料 |
| IBM Documentation | 产品手册、模型参数和操作说明 | 技术支持资料 |
| 政府或高校公开制度 | 报销、采购、行政和信息安全流程 | 中文制度资料 |

所有原始资料必须记录：

- 标题与来源 URL；
- 获取日期；
- 原始语言；
- 许可证或公开使用说明；
- 改写或节选情况。

本实验不声称资料来自真实保密企业内网。对外描述应使用“基于公开企业资料构建的模拟企业知识库”。

## 4. 文档组成

统一将语料组织为虚构企业“星云科技”的内部知识库，保留公开资料中的真实流程复杂度，但不冒充原公司的真实内部制度。

| 类别 | 数量 | 示例 |
|---|---:|---|
| IT 与产品技术文档 | 12 | 系统接入、账号权限、模型参数、故障处理 |
| 安全、隐私与合规 | 7 | 数据分级、设备安全、访问控制 |
| HR 与行政制度 | 8 | 入职、休假、缺勤、远程办公、差旅 |
| 财务、采购与报销 | 6 | 报销额度、审批链、供应商采购 |
| 项目管理与会议资料 | 7 | 项目启动、周会纪要、复盘和变更记录 |
| 旧版、近重复和冲突文档 | 5 | v1/v2 制度、草案、过期 FAQ |
| **合计** | **45** | 中英混合 |

### 4.1 文档元数据

每份文档至少包含：

```yaml
document_id: hr-travel-policy-v2
title: 员工差旅与报销制度
department: HR
document_type: policy
language: zh-CN
version: "2.0"
published_at: "2026-01-01"
effective_from: "2026-02-01"
effective_to: null
status: active
authority_level: official_policy
supersedes: hr-travel-policy-v1
source_url: https://example.com/source
license: CC-BY-4.0
```

其中 `status` 和 `authority_level` 是版本与冲突实验的关键字段。

建议权威等级：

1. `official_policy`
2. `official_manual`
3. `approved_faq`
4. `meeting_minutes`
5. `draft`
6. `archived`

## 5. QA 基准设计

共设计 30 道题：

| 类型 | 数量 | 主要能力 |
|---|---:|---|
| 单文档事实题 | 8 | 基础检索与事实提取 |
| 条件和例外题 | 5 | 理解适用范围、条件与例外 |
| 跨文档综合题 | 4 | 聚合多个部门或流程信息 |
| 新旧版本题 | 4 | 选择当前生效版本 |
| 冲突与权威性题 | 3 | 区分正式制度、草案和会议纪要 |
| 无答案拒答题 | 3 | 避免编造 |
| 中英跨语言题 | 3 | 中文提问检索英文资料 |
| **合计** | **30** | — |

### 5.1 QA 数据结构

```json
{
  "question_id": "version-001",
  "question": "2026 年员工国内住宿的有效报销上限是多少？",
  "ground_truth": "当前有效制度规定为每晚 600 元。",
  "answerable": true,
  "question_type": "version",
  "gold_documents": ["hr-travel-policy-v2"],
  "gold_passages": ["国内住宿费用上限为每晚 600 元。"],
  "expected_version": "2.0",
  "expected_authority_level": "official_policy",
  "language_route": "zh-to-zh",
  "notes": "旧版制度中的上限为 500 元。"
}
```

无答案题必须设置：

```json
{
  "answerable": false,
  "gold_documents": [],
  "expected_behavior": "明确说明知识库未提供该信息，不推测具体数值"
}
```

### 5.2 QA 制作流程

1. LLM 根据指定文档生成候选问题、答案和证据段落。
2. 脚本检查 `gold_documents` 与 `gold_passages` 是否真实存在。
3. 人工逐题审核答案、适用条件、版本和文档权威性。
4. 对无答案题执行全库关键词检查，避免存在意外答案。
5. 冻结最终 30 题，实验期间不得根据结果修改标准答案。

LLM 只负责生成候选内容，不能代替最终人工审核。

## 6. 对照实验

### 6.1 三组语料环境

| 组别 | 语料环境 | 目的 |
|---|---|---|
| E0 Clean | 每题相关文档及少量基础资料 | 建立理想环境上限 |
| E1 Mixed | 加入全部普通跨部门文档 | 测试企业多部门噪声 |
| E2 Conflict | 在 E1 上加入旧版、近重复、草案和冲突资料 | 测试真实高风险场景 |

E0、E1、E2 使用相同的 30 道题。每组只改变可检索语料，其他配置全部冻结。

### 6.2 固定变量

- Chunker 与 chunk 参数；
- Embedding 模型；
- Hybrid Retrieval 与 RRF 参数；
- BGE Reranker；
- Top-20 候选、Reranker Top-5；
- 0.50 绝对阈值、0.75 相对阈值、至少保留 3 条；
- Query Rewrite 模型与 Prompt；
- MiMo T02 生成模型与 Prompt；
- RAGAS Judge 模型和参数。

### 6.3 运行顺序

1. 为 E0、E1、E2 分别建立独立 Chroma 集合。
2. 每组先运行 5 道冒烟测试。
3. 每组捕获并保存检索上下文。
4. 使用冻结上下文生成答案。
5. 运行 RAGAS。
6. 运行确定性检索和业务指标计算。
7. 汇总性能衰减、失败题和典型案例。

所有产物按组隔离，禁止覆盖当前 watsonxDocsQA 基线。

## 7. 评价指标

### 7.1 RAGAS 指标

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

由于当前实验已观察到 LLM Judge 波动，分差小于 `0.05` 不单独作为优化结论。关键版本至少重复评测 2 次；若两次结论方向不一致，再运行第 3 次。

### 7.2 确定性检索指标

| 指标 | 定义 |
|---|---|
| Document Hit@5 | Top-5 是否包含任一 gold document |
| Passage Hit@5 | Top-5 是否包含 gold passage 或其对应 chunk |
| MRR | 首个正确文档的倒数排名 |
| Context Recall | 标准答案证据被召回的比例 |

### 7.3 企业场景指标

| 指标 | 定义 |
|---|---|
| Active Version Accuracy | 版本题是否命中当前生效文档 |
| Authority Accuracy | 冲突题是否优先采用更高权威文档 |
| Abstention Accuracy | 无答案题是否正确拒答 |
| Unsupported Claim Rate | 回答中无上下文支持的关键断言比例 |
| Citation Accuracy | 引用的文档是否确实支持答案 |
| Cross-language Hit@5 | 跨语言题的正确文档命中率 |

版本题和冲突题不能只依赖 RAGAS 判断，必须结合 `document_id`、`version`、`status` 和人工规则评分。

### 7.4 工程指标

- 平均与 P95 端到端延迟；
- Rewrite、Retrieval、Rerank、Generate 分阶段耗时；
- 每题候选 chunk 数和最终上下文数；
- 生成与 Judge 的 Token 使用量；
- 单组实验总耗时。

## 8. 成功判据

首轮实验不要求所有指标超过当前 watsonxDocsQA 分数。成功的标准是得到稳定、可解释的企业混杂语料结论。

建议目标：

| 指标 | E1 目标 | E2 目标 |
|---|---:|---:|
| Document Hit@5 | ≥ 0.90 | ≥ 0.80 |
| Active Version Accuracy | ≥ 0.85 | ≥ 0.75 |
| Authority Accuracy | ≥ 0.80 | ≥ 0.70 |
| Abstention Accuracy | ≥ 0.80 | ≥ 0.80 |
| Faithfulness | ≥ 0.85 | ≥ 0.80 |
| Answer Relevancy | ≥ 0.80 | ≥ 0.75 |

同时满足以下条件才可声称某项优化有效：

1. 目标指标提升至少 `0.05`，或确定性指标提升至少 2 道题；
2. Faithfulness 不下降超过 `0.03`；
3. 至少一个典型失败案例被明确修复；
4. 改动在 E0 上没有造成明显回归。

## 9. 预期失败与后续优化

优先诊断以下失败：

1. **正确文档未进入 Top-20**：Embedding、Rewrite 或语义召回问题。
2. **Top-20 有正确文档但 Top-5 丢失**：Reranker 问题。
3. **Top-5 有新版和旧版但旧版排名更高**：缺少版本与状态特征。
4. **上下文正确但回答采用错误口径**：Prompt 或生成模型问题。
5. **无答案题强行作答**：拒答策略问题。
6. **中英跨语言题未召回**：跨语言 Embedding 或 Rewrite 问题。

首轮只做诊断，不预先实现复杂方案。若 E2 的主要问题确实来自版本冲突，再考虑：

- 在检索结果中加入版本、生效日期和权威等级；
- 对 `archived` 和 `draft` 文档降权；
- 同主题文档按 `supersedes` 关系去重；
- 在生成 Prompt 中明确“正式生效制度优先于会议纪要和草案”。

## 10. 实验产物

建议目录：

```text
data/enterprise_mixed/
├── sources/                    # 来源清单和许可证记录
├── documents/
│   ├── clean/
│   ├── mixed/
│   └── conflict/
├── qa/
│   └── enterprise_qa_30.json
├── contexts/
│   ├── e0_contexts.json
│   ├── e1_contexts.json
│   └── e2_contexts.json
└── reports/
    ├── e0_ragas.json
    ├── e1_ragas.json
    ├── e2_ragas.json
    └── enterprise_benchmark_summary.json
```

最终展示材料：

- E0 → E1 → E2 指标衰减折线图；
- 各题型能力雷达图；
- 检索命中率与 RAGAS 对照表；
- 新旧版本冲突案例；
- 无答案正确拒答案例；
- 优化前后对比图。

## 11. 简历与面试表述

推荐表述：

> 基于 GitLab Handbook、GitHub Policies、Atlassian Team Playbook 等公开企业资料，构建中英混合企业知识库压力基准；设计 30 道带文档证据、版本状态与可回答性标注的 QA，在多部门噪声、近重复和版本冲突环境下评估 RAG 的检索、版本选择与拒答能力。

实验完成后再补充真实结果，例如：

> 通过版本感知检索与权威等级重排，将有效版本命中率从 X% 提升至 Y%，并将混杂语料下的错误引用率降低 Z%。

结果数字只能在正式实验完成后填写。

## 12. 执行边界

首轮明确不做：

- 1000 份以上大规模语料；
- 权限隔离与多租户；
- OCR 和扫描件识别；
- 多模态图片问答；
- 复杂知识图谱；
- 全自动无人工审核 QA；
- 为提高 RAGAS 分数而修改标准答案。

完成 E0/E1/E2 后，根据失败分布决定是否进入版本感知检索优化，不提前扩大范围。
