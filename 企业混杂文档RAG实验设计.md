# 企业混杂文档 RAG 实验设计

> 版本：v1.1
> 日期：2026-06-08
> 目标：从公开网络拉取真实混杂企业文档，构建可复现的内部知识库压力基准，验证 RAG 在噪声、近重复、版本冲突和无答案场景下的稳定性。
> 原则：服务简历展示与面试讲解，优先追求高信息密度和可解释结论，不追求超大规模。真实文档优于 LLM 改写——保留原始格式不一致、术语混用等自然噪声。

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

| 项目 | 规模 |
|---|---:|
| 从公开网络采集的原始文档 | 约 60-80 篇 |
| 经最小处理后入库的文档 | 约 45-55 份 |
| 含中文文档 | 10-15 份 |
| 含过期/废弃文档 | 3-5 份 |
| 人工审核 QA | 36 题（7 类 × 4-8 题/类） |
| 压力等级 | 3 组 (E0 Clean / E1 Mixed / E2 Conflict) |
| 生产生成配置 | MiMo v2.5 Pro，非思考，temperature=0.2 |
| Judge | MiMo v2.5 Pro，thinking enabled |

预计投入：

- 网络采集与格式处理：2-3 小时；
- 文档审查、分类与 metadata 标注：1-2 小时；
- QA 生成与人工审核：3-4 小时；
- ChromaDB 重建与摄入：0.5 小时；
- 三组实验运行与分析：3-4 小时。

总计约 1.5 个工作日。若首轮无法形成清晰结论，不盲目扩大规模，而是聚焦失败案例做定向修复。

## 3. 公开资料来源（真实文档，非 LLM 改写）

核心策略：**直接从公开网络拉取真实企业/组织文档，仅替换公司名为「星云科技」，其余格式、术语、结构全部保留原样。** 真实文档自带格式不一致、术语混用、重复内容、过时页面等噪声——这些是 LLM 改写会抹平的、本实验恰恰需要的特征。

### 3.1 英文源（技术管理 + 安全合规 + 人力资源）

| 来源 | 可采量 | 噪声特征 | 用途 |
|------|:--:|------|------|
| **GitLab Handbook** (handbook.gitlab.com) | ~50 篇 | 跨部门（HR/安全/工程/财务/差旅）、有版本历史、有明确废弃页面标记 | 企业制度主体 |
| **Mozilla Wiki** (wiki.mozilla.org) | ~20 篇 | 格式极度不统一——Security Policy、RFC、会议纪要、发布流程混在一起，部分页面已标记 outdated | 混杂噪声源 + 版本冲突 |
| **18F Methods & Guides** (18f.gsa.gov) | ~10 篇 | 政府数字化服务方法论、安全合规检查清单、采购审批流程 | 安全与合规资料 |
| **Apache Foundation** (apache.org/foundation) | ~8 篇 | 发布流程、安全漏洞处理、社区行为准则、投票决策机制 | 技术治理 |
| **Ubuntu Community Governance** (ubuntu.com/community/governance) | ~5 篇 | 技术委员会决策记录、行为准则 | 决策记录样例 |
| **Debian Policy Manual** (debian.org/doc/devel-manuals) | ~5 篇 | 极其技术化、版本规则密集、格式为纯文本 | 技术手册 |
| **Basecamp Employee Handbook** (公开版) | ~8 篇 | 真实简洁的员工手册、休假/福利/远程办公制度 | HR 制度 |

### 3.2 中文源（制度 + 行政 + 技术）

| 来源 | 可采量 | 噪声特征 | 用途 |
|------|:--:|------|------|
| **高校信息化办公室公开制度**（北大/清华/上交等） | ~10 篇 | 网络管理规定、数据安全办法、机房管理制度——真实的中文制度措辞 | 中文制度主体 |
| **中国政府开放数据/信息公开政策** | ~5 篇 | 数据分级分类、安全审查、个人信息保护 | 中文合规 |
| **知名开源社区中文文档**（Apache CN/OSChina/开放原子等） | ~5 篇 | 贡献指南、社区规范、发布流程的中文表述 | 中文技术管理 |
| **华为云/阿里云公开产品文档（节选）** | ~5 篇 | 中文技术操作手册、参数说明、故障处理 | 中文技术支持 |

### 3.3 主动保留的混杂元素

采集时刻意不做以下事：

- **不统一标题层级**：Mozilla Wiki 用 `=` 下划线标题，GitLab 用 `#` markdown，Debian 用纯文本编号——全保留
- **不统一术语**：「access token」/「personal access token」/「PAT」/「令牌」在不同文档中混用
- **不修过时内容**：标记为 `deprecated`/`outdated`/`archived` 的页面保留入库，用 metadata 标注状态
- **不删重复内容**：GitLab 和 18F 可能都有「安全漏洞报告流程」，两个版本各有表述差异，同时入库
- **不补元数据**：原始文档缺发布日期或缺作者的不补，真实企业知识库也不会有完整元数据

### 3.4 最小处理规则

对每篇原始文档只做以下操作：

1. **公司名替换**：`GitLab`/`Mozilla`/`18F`/`Apache` → `星云科技`；对应 URL 替换为 `stardust.tech`
2. **添加 YAML frontmatter**（仅能确定的字段）：

```yaml
document_id: stardust-hr-travel
title: 员工差旅与报销制度
department: HR
document_type: policy
language: en
status: active          # active | draft | archived | deprecated
authority_level: official_policy
source_url: https://handbook.gitlab.com/...  # 原始 URL 保留
license: CC-BY-SA-4.0
ingested_at: 2026-06-08
```

3. **不改变正文任何内容**：格式、段落、列表、代码块全部原样保留

所有原始资料在 `data/enterprise_mixed/sources/source_manifest.csv` 中记录：

```csv
document_id,title,source_url,original_date,language,license,status,notes
```

本实验不声称资料来自真实保密企业内网。对外描述使用”基于 GitLab/Mozilla/Apache 等组织的公开文档构建的模拟企业知识库”。

## 4. 文档组成

统一将语料组织为虚构企业「星云科技」的内部知识库，保留原始文档中的真实流程复杂度，仅将公司名称和 URL 替换。

| 类别 | 数量 | 示例 |
|---|---:|---|
| IT 与产品技术文档 | 10-12 | 系统接入、账号权限、API 参数、故障处理、发布流程 |
| 安全、隐私与合规 | 8-10 | 数据分级、漏洞报告、设备安全、访问控制、安全审计 |
| HR 与行政制度 | 8-10 | 入职离职、休假、缺勤、远程办公、差旅报销 |
| 财务、采购与报销 | 5-7 | 报销额度、审批链、供应商采购流程 |
| 项目管理与会议资料 | 6-8 | 项目启动、周会纪要、复盘总结、变更记录 |
| **主动保留的旧版/废弃/冲突文档** | **5-8** | v1/v2 制度、过期 FAQ、标记为 deprecated 的安全策略 |
| **合计** | **45-55** | 中英混合，原始格式 |

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

共 36 题。每类型至少 4 题以保证分维度分析的最低统计可解释性（能区分 2 题/4 题的差异 vs 随机波动）。

| 类型 | 数量 | 主要能力 |
|---|---:|---|
| 单文档事实题 | 8 | 基础检索与事实提取 |
| 条件和例外题 | 4 | 理解适用范围、条件与例外 |
| 跨文档综合题 | 5 | 聚合多个部门或流程信息 |
| 新旧版本题 | 5 | 选择当前生效版本而非旧版 |
| 冲突与权威性题 | 5 | 区分正式制度、草案和会议纪要 |
| 无答案拒答题 | 4 | 避免编造 |
| 中英跨语言题 | 5 | 中文提问检索英文资料 |
| **合计** | **36** | — |

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
5. 冻结最终 36 题，实验期间不得根据结果修改标准答案。

LLM 只负责生成候选内容，不能代替最终人工审核。

## 6. 对照实验

### 6.1 三组语料环境

E0、E1、E2 使用相同的 36 道题。每组只改变可检索语料，其他配置全部冻结。

| 组别 | 语料规模 | 目的 |
|---|---|---|
| E0 Clean | ~15 篇（gold_documents + 基础 IT 文档） | 建立无干扰天花板 |
| E1 Mixed | ~50 篇（E0 + 全部普通跨部门文档） | 测试企业多部门噪声 |
| E2 Conflict | ~55 篇（E1 + 旧版/草案/过期/冲突文档） | 测试真实高危场景 |

### 6.2 各组语料清单

#### 6.2.1 E0 Clean 语料（~15 篇）

E0 语料 = **QA gold_documents 全集**（~10 篇，取决于 36 题实际引用覆盖）+ **5 篇星云科技企业基础文档**（不参与答题但提供企业背景语境）。

5 篇固定基础文档（独立于 QA 设计）：

| document_id | 标题 | 来源 | 语言 | 内容 |
|---|---|---|---|---|
| `stardust-it-overview` | 星云科技 IT 系统总览 | GitLab Handbook / IT 部分 | en | 公司使用的核心系统、统一认证、网络拓扑简介 |
| `stardust-hr-onboarding` | 新员工入职指南 | GitLab Handbook / Onboarding | en | 入职流程、系统账号开通、设备领取 |
| `stardust-sec-basics` | 员工信息安全基本守则 | Mozilla Wiki / Security | en | 密码管理、VPN 使用、数据分类基本概念 |
| `stardust-admin-glossary` | 行政术语表 | GitLab Handbook / Glossary | en | 公司内部通用术语和缩写 |
| `stardust-corp-overview` | 星云科技公司概况 | 自编（200 字以内） | zh | 公司业务、部门架构、办公地点简述 |

其余 ~10 篇为 QA 中 `gold_documents` 引用的文档，在 QA 完成后确定。E0 **不包含**任何旧版文档、草案、过期页面或重复内容。

#### 6.2.2 E1 Mixed 在 E0 基础上新增（~35 篇，合计约 50 篇）

从 §3 所述来源拉取的所有「普通」文档——不含任何旧版/过期/冲突/重复内容。

| 类别 | 新增量 | 来源 |
|---|---|---|
| IT 与产品技术文档 | 8-10 | GitLab Handbook (IT/Engineering)、Debian Policy Manual、Apache Governance |
| 安全、隐私与合规 | 7-9 | Mozilla Wiki (Security)、18F Methods (Security & Compliance)、Apache Security |
| HR 与行政制度 | 7-9 | GitLab Handbook (HR/People)、Basecamp Handbook |
| 财务、采购与报销 | 4-6 | GitLab Handbook (Finance/Procurement)、18F Methods (Procurement) |
| 项目管理与会议资料 | 5-7 | Mozilla Wiki (Meeting Notes/RFCs)、Ubuntu Governance (Board Notes) |
| 中文制度与技术文档 | 8-10 | 高校信息化制度、政府开放数据政策、华为云/阿里云产品文档 |
| **合计新增** | **~39-51** | 取整后实际入库约 35 篇（筛选掉过于碎片化或冗余的页面） |

#### 6.2.3 E2 Conflict 在 E1 基础上新增（5-8 篇，合计约 55 篇）

| document_id | 标题 | 冲突类型 | 来源 | 说明 |
|---|---|---|---|---|
| `stardust-hr-travel-v1` | 员工差旅制度 v1.0 | 旧版 | GitLab Handbook / 旧版本 | 规定住宿上限 500 元/晚，已被 v2.0 取代 |
| `stardust-sec-vuln-v1` | 安全漏洞报告流程 v1.0 | 旧版 | Mozilla Wiki / 旧版安全策略 | 旧的 5 天响应 SLA，新标准为 48 小时 |
| `stardust-it-access-draft` | 系统权限申请制度（草案） | 草案 | Apache / 未发布草案 | 标记 status=draft，与正式制度存在口径差异 |
| `stardust-procurement-faq-v0` | 供应商采购 FAQ（过期） | 过期 | GitLab Handbook / 标记 deprecated 的旧 FAQ | 引用已废止的审批链 |
| `stardust-remote-policy-minutes` | 远程办公制度讨论纪要 | 会议纪要 | Mozilla Wiki / Meeting Notes | 与正式远程办公制度表述不一致，权威等级低 |
| `stardust-data-class-dup` | 数据分级标准（社区版） | 近重复 | 18F Methods | 与官方 `stardust-sec-data-class` 内容高度重叠但细节有出入 |

E2 的核心特征：同一个问题可能同时命中 `stardust-hr-travel-v2`（生效版）和 `stardust-hr-travel-v1`（旧版），系统必须在无版本感知机制的情况下自行区分。

### 6.3 全部语料对比

| 特征 | E0 Clean | E1 Mixed | E2 Conflict |
|------|:--:|:--:|:--:|
| 文档数 | ~15 | ~50 | ~55 |
| 跨部门噪声 | 无 | 有 | 有 |
| 中英混合 | 少量 | 有 | 有 |
| 过时/废弃内容 | 无 | 无 | 有（5-8 篇） |
| 旧版本冲突 | 无 | 无 | 有 |
| 会议纪要 vs 正式制度 | 无 | 无 | 有 |
| 近重复文档 | 无 | 无 | 有 |

### 6.4 固定变量

- Chunker 与 chunk 参数；
- Embedding 模型；
- Hybrid Retrieval 与 RRF 参数；
- BGE Reranker；
- Top-20 候选、Reranker Top-5；
- 0.50 绝对阈值、0.75 相对阈值、至少保留 3 条；
- Query Rewrite 模型与 Prompt；
- MiMo T02 生成模型与 Prompt；
- RAGAS Judge 模型和参数。

### 6.5 运行顺序

1. 从公开网络采集原始文档，执行最小处理（公司名替换 + YAML frontmatter），存入 `data/enterprise_mixed/documents/`
2. 为 E0、E1、E2 分别建立独立 ChromaDB 集合（三个集合使用不同前缀隔离，确保 E0 Clean 无干扰）
3. 各组独立摄入文档到对应 ChromaDB 集合
4. 重建 BM25 索引
5. 每组先运行 5 道冒烟测试（覆盖检索、生成、SSE 流）
6. 每组捕获并保存检索上下文（复用现有 `gen_one.py --capture-contexts` 机制）
7. 使用冻结上下文生成答案（`gen_one.py --reuse-contexts`，各题型统一用 MiMo T02）
8. 运行 RAGAS（每组一次）
9. 仅当某组 RAGAS 差异 > 0.05 且与确定性指标矛盾时，对该组复评一次
10. 汇总性能衰减、失败题和典型案例

所有产物按组隔离，禁止覆盖当前 watsonxDocsQA 基线的数据和 ChromaDB 集合。

## 7. 评价指标

### 7.1 RAGAS 指标

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

### 7.2 重测协议（单次运行 + 条件复评）

基于 watsonxDocsQA 实验的实测结论——同一检索上下文被同一 Judge 评两次，Context Precision 配对差异 SD=0.25，Faithfulness 相对最稳定但仍有波动——采用以下轻量协议：

**默认：每实验组 (E0/E1/E2) 只跑一次完整 RAGAS。**

**决策规则**：

1. **确定性指标做主判断**：Document Hit@5、MRR、Active Version Accuracy、Authority Accuracy、Abstention Accuracy 均无 Judge 噪声，优先依据这些指标做结论。
2. **RAGAS 辅助参考**：分差 < 0.05 不做结论，报告中标注「单次 RAGAS 评测，±0.05 测量不确定度」。
3. **条件复评**：仅当某组 RAGAS 差异 > 0.05 **且**与确定性指标方向矛盾时（例如 Faithfulness 升 0.07 但 Document Hit@5 下降），才对该组重新运行 RAGAS 一次取均值。

**复评只跑 Judge 不跑生成**：若触发复评，直接对已有答案文件重新运行 `eval_ragas_only.py`，不重新生成答案。

### 7.3 确定性检索指标

| 指标 | 定义 |
|---|---|
| Document Hit@5 | Top-5 是否包含任一 gold document |
| Passage Hit@5 | Top-5 是否包含 gold passage 或其对应 chunk |
| MRR | 首个正确文档的倒数排名 |
| Context Recall | 标准答案证据被召回的比例 |

### 7.4 企业场景指标

| 指标 | 定义 |
|---|---|
| Active Version Accuracy | 版本题是否命中当前生效文档 |
| Authority Accuracy | 冲突题是否优先采用更高权威文档 |
| Abstention Accuracy | 无答案题是否正确拒答 |
| Unsupported Claim Rate | 回答中无上下文支持的关键断言比例 |
| Citation Accuracy | 引用的文档是否确实支持答案 |
| Cross-language Hit@5 | 跨语言题的正确文档命中率 |

版本题和冲突题不能只依赖 RAGAS 判断，必须结合 `document_id`、`version`、`status` 和人工规则评分。

### 7.5 工程指标

- 平均与 P95 端到端延迟；
- Rewrite、Retrieval、Rerank、Generate 分阶段耗时；
- 每题候选 chunk 数和最终上下文数；
- 生成与 Judge 的 Token 使用量；
- 单组实验总耗时。

## 8. 成功判据

首轮实验不要求所有指标超过当前 watsonxDocsQA 分数。成功标准是**得到稳定、可解释的企业混杂语料结论，形成清晰的面试展示材料**。

### 8.1 各环境目标

| 指标 | 指标类型 | E1 目标 | E2 目标 |
|---|---:|---|---:|
| Document Hit@5 | 确定性 | ≥ 0.90 | ≥ 0.80 |
| Active Version Accuracy | 确定性 | ≥ 0.85 | ≥ 0.75 |
| Authority Accuracy | 确定性 | ≥ 0.80 | ≥ 0.70 |
| Abstention Accuracy | 确定性 | ≥ 0.80 | ≥ 0.80 |
| Faithfulness | RAGAS | ≥ 0.85 | ≥ 0.80 |
| Answer Relevancy | RAGAS | ≥ 0.80 | ≥ 0.75 |

### 8.2 效应量判据（替代绝对值阈值）

基于实测 Judge 噪声水平，以下条件**同时满足**才可声称某项优化有效：

1. **确定性指标**：Document Hit@5 或 Active Version Accuracy 提升 ≥ 2 道题（不受 Judge 噪声影响）；
2. **Cohen's d**：目标指标（如 Faithfulness）的 Cohen's d ≥ 0.5（中等效应），或两次 RAGAS 复评结论方向一致；
3. **无显著回归**：Faithfulness 的 Cohen's d 不低于 -0.3（不超过小效应的反向退化）；
4. **有案例支撑**：至少一个典型失败案例被明确修复；
5. **无 E0 污染**：改动在 E0 上没有出现可观察的性能下降。

理由：实测 Judge 在 Context Precision 上的 SD=0.25，要求「Faithfulness 不降超 0.03」超出了测量系统精度。改用效应量判据，使成功标准与测量能力匹配。

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
│   └── enterprise_qa_36.json
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

> 基于 GitLab Handbook、Mozilla Wiki、18F 政府数字化指南、Debian Policy Manual 等真实公开组织文档，构建中英混合企业知识库压力基准；从网络直接采集、保留原始格式噪声与过时内容，仅做公司名替换；设计 36 道带文档证据、版本状态与可回答性标注的 QA，在多部门噪声、近重复和版本冲突环境下评估 RAG 的检索、版本选择与拒答能力。

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
