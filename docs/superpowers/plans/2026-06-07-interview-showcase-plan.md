# Interview Showcase Implementation Plan

> Historical implementation plan. Score assertions below describe the state at
> authoring time. Current production scores are MiMo T02
> `0.946 / 0.876 / 0.869`; D4P Frozen is `0.968 / 0.851 / 0.831`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the repository into an interview-friendly RAG case study with traceable evaluation data, seven polished diagrams, and a high-impact README without changing runtime behavior.

**Architecture:** Keep `backend/` and all runtime imports in place. Add a standard-library SVG asset generator backed by one JSON data source, move only documentation and standalone history files, then rebuild the README around evidence, architecture, and representative debugging cases.

**Tech Stack:** Markdown, JSON, Python 3.12 standard library, SVG, pytest, Git, GitHub README rendering

---

## File Map

**Create**

- `assets/diagrams/showcase-data.json` - canonical values and labels used by every evaluation diagram.
- `assets/diagrams/*.svg` - seven generated diagrams.
- `assets/diagrams/previews/*.png` - browser-rendered previews for the hero and core charts.
- `scripts/maintenance/generate_showcase_assets.py` - deterministic SVG generator.
- `scripts/maintenance/validate_showcase.py` - repository link, asset, and data consistency checks.
- `backend/tests/test_showcase_assets.py` - tests for data integrity, generated assets, and README references.
- `docs/architecture/system-architecture.md` - detailed component and data-flow explanation.
- `docs/case-study/evaluation-integrity.md` - RAGAS truncation incident case study.
- `docs/case-study/retrieval-and-prompt-debugging.md` - Q00/Q02 diagnosis and threshold experiment.
- `docs/evaluation/README.md` - evaluation entry point and validity rules.
- `docs/handoff/README.md` - index for AI collaboration and handoff records.
- `docs/archive/README.md` - archive semantics.

**Move**

- `14.06claude写这里/迭代记录_全量RAGAS分数.md` -> `docs/evaluation/ragas-iteration-history.md`
- `ragabilitytest.md` -> `docs/evaluation/ragas-report.md`
- `data/evaluations/reports/ragas_filter_experiment_2026-06-06.md` -> `docs/evaluation/adaptive-filter-experiment.md`
- `14.06claude写这里/README.md` -> `docs/handoff/claude-handoff-index.md`
- `14.06claude写这里/ChatGPT交接_当前状态与纠结点_2026-06-06.md` -> `docs/handoff/chatgpt-current-state-2026-06-06.md`
- `14.06claude写这里/RAG项目交接文档_2026-06-06.md` -> `docs/handoff/rag-project-handoff-2026-06-06.md`
- `14.06claude写这里/项目文档与实现审计报告_2026-06-06.md` -> `docs/handoff/document-audit-2026-06-06.md`
- `CHATGPT_README.md` -> `docs/handoff/codex-worklog.md`
- `claude_memory/*.md` -> `docs/archive/claude-memory/*.md`

**Modify**

- `.gitignore` - ignore `.superpowers/`.
- `README.md` - replace current overview with the approved A+C narrative and B-style data visuals.
- `docs/README.md` - become the canonical documentation index.
- `docs/research/README.md` - repair links after moves.
- Handoff and archive Markdown files - repair relative links only.

---

### Task 1: Establish the Canonical Showcase Dataset

**Files:**

- Modify: `.gitignore`
- Create: `assets/diagrams/showcase-data.json`
- Create: `backend/tests/test_showcase_assets.py`

- [ ] **Step 1: Write the failing data integrity tests**

Create `backend/tests/test_showcase_assets.py` with:

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "assets" / "diagrams" / "showcase-data.json"


def load_data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_showcase_data_records_current_baseline():
    data = load_data()
    f2 = next(row for row in data["iterations"] if row["id"] == "F2")
    assert f2["status"] == "current"
    assert f2["faithfulness"] == 0.918
    assert f2["answer_relevancy"] == 0.826
    assert f2["context_precision"] == 0.844


def test_truncated_and_non_end_to_end_runs_are_explicit():
    data = load_data()
    statuses = {row["id"]: row["status"] for row in data["iterations"]}
    assert statuses["GT"] == "upper_bound"
    assert all(statuses[name] == "contaminated" for name in ("L4", "L5", "L6"))


def test_threshold_experiment_selects_balanced_f2():
    data = load_data()
    rows = {row["label"]: row for row in data["thresholds"]}
    assert rows["0.75"]["selected"] is True
    assert rows["0.75"]["mean"] == 0.863
    assert rows["0.80"]["faithfulness"] > rows["0.75"]["faithfulness"]
    assert rows["0.80"]["answer_relevancy"] < rows["0.75"]["answer_relevancy"]
```

- [ ] **Step 2: Run the tests and verify the missing dataset failure**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py -q
```

Expected: FAIL because `assets/diagrams/showcase-data.json` does not exist.

- [ ] **Step 3: Add the canonical JSON dataset**

Create `assets/diagrams/showcase-data.json` with this structure and values:

```json
{
  "meta": {
    "dataset": "watsonxDocsQA",
    "questions": 30,
    "current_baseline": "F2",
    "generated_at": "2026-06-07"
  },
  "iterations": [
    {"id":"L0","faithfulness":0.566,"answer_relevancy":0.672,"context_precision":0.560,"status":"historical"},
    {"id":"L1","faithfulness":0.610,"answer_relevancy":0.770,"context_precision":0.550,"status":"historical"},
    {"id":"L2","faithfulness":0.544,"answer_relevancy":0.753,"context_precision":0.865,"status":"historical"},
    {"id":"L3","faithfulness":0.540,"answer_relevancy":0.762,"context_precision":0.614,"status":"historical"},
    {"id":"GT","faithfulness":0.864,"answer_relevancy":0.897,"context_precision":0.911,"status":"upper_bound"},
    {"id":"L4","faithfulness":0.498,"answer_relevancy":0.784,"context_precision":0.730,"status":"contaminated"},
    {"id":"L5","faithfulness":0.451,"answer_relevancy":0.791,"context_precision":0.721,"status":"contaminated"},
    {"id":"L6","faithfulness":0.469,"answer_relevancy":0.808,"context_precision":0.701,"status":"contaminated"},
    {"id":"F0","faithfulness":0.874,"answer_relevancy":0.818,"context_precision":0.816,"status":"formal"},
    {"id":"F1","faithfulness":0.901,"answer_relevancy":0.791,"context_precision":0.834,"status":"formal"},
    {"id":"F2","faithfulness":0.918,"answer_relevancy":0.826,"context_precision":0.844,"status":"current"},
    {"id":"F3","faithfulness":0.937,"answer_relevancy":0.780,"context_precision":0.799,"status":"formal"}
  ],
  "thresholds": [
    {"label":"off","contexts":5.00,"faithfulness":0.874,"answer_relevancy":0.818,"context_precision":0.816,"mean":0.836,"selected":false},
    {"label":"0.70","contexts":4.47,"faithfulness":0.901,"answer_relevancy":0.791,"context_precision":0.834,"mean":0.842,"selected":false},
    {"label":"0.75","contexts":4.10,"faithfulness":0.918,"answer_relevancy":0.826,"context_precision":0.844,"mean":0.863,"selected":true},
    {"label":"0.80","contexts":3.83,"faithfulness":0.937,"answer_relevancy":0.780,"context_precision":0.799,"mean":0.839,"selected":false}
  ]
}
```

- [ ] **Step 4: Ignore visual brainstorming state**

Append to `.gitignore`:

```gitignore

# Local visual brainstorming sessions
.superpowers/
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit the data foundation**

```powershell
git add .gitignore assets/diagrams/showcase-data.json backend/tests/test_showcase_assets.py
git commit -m "test: lock showcase evaluation data"
```

---

### Task 2: Build the Deterministic SVG Generator

**Files:**

- Create: `scripts/maintenance/generate_showcase_assets.py`
- Modify: `backend/tests/test_showcase_assets.py`
- Create: `assets/diagrams/ragas-iteration-trend.svg`
- Create: `assets/diagrams/valid-experiment-progress.svg`
- Create: `assets/diagrams/threshold-comparison.svg`
- Create: `assets/diagrams/rag-system-architecture.svg`
- Create: `assets/diagrams/retrieval-decision-flow.svg`
- Create: `assets/diagrams/failure-analysis-loop.svg`
- Create: `assets/diagrams/engineering-capability-map.svg`

- [ ] **Step 1: Add failing generator tests**

Append:

```python
import subprocess
import sys


EXPECTED_DIAGRAMS = {
    "ragas-iteration-trend.svg",
    "valid-experiment-progress.svg",
    "threshold-comparison.svg",
    "rag-system-architecture.svg",
    "retrieval-decision-flow.svg",
    "failure-analysis-loop.svg",
    "engineering-capability-map.svg",
}


def test_generator_creates_all_diagrams(tmp_path):
    script = ROOT / "scripts" / "maintenance" / "generate_showcase_assets.py"
    subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
    )
    assert {path.name for path in tmp_path.glob("*.svg")} == EXPECTED_DIAGRAMS
    for path in tmp_path.glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<svg")
        assert 'viewBox="0 0 1600 900"' in text
        assert "0.918" in text or path.name not in {
            "valid-experiment-progress.svg",
            "threshold-comparison.svg",
        }


def test_generated_diagrams_do_not_claim_industry_standards(tmp_path):
    script = ROOT / "scripts" / "maintenance" / "generate_showcase_assets.py"
    subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.glob("*.svg")
    )
    assert "行业标准" not in combined
    assert "企业标准" not in combined
```

- [ ] **Step 2: Verify the generator test fails**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py::test_generator_creates_all_diagrams -q
```

Expected: FAIL because the generator script does not exist.

- [ ] **Step 3: Implement the SVG generator**

Create a Python 3 standard-library CLI with:

```python
def load_data(path: Path) -> dict: ...
def svg_document(title: str, subtitle: str, body: str) -> str: ...
def text(x: int, y: int, value: str, *, size: int, color: str, weight: int = 400) -> str: ...
def line(x1: int, y1: int, x2: int, y2: int, *, color: str, width: int = 2, dash: str | None = None) -> str: ...
def rect(x: int, y: int, width: int, height: int, *, fill: str, stroke: str = "none", radius: int = 0) -> str: ...
def polyline(points: list[tuple[int, int]], *, color: str, width: int = 4, dash: str | None = None) -> str: ...
def render_iteration_trend(data: dict) -> str: ...
def render_valid_progress(data: dict) -> str: ...
def render_threshold_comparison(data: dict) -> str: ...
def render_system_architecture(data: dict) -> str: ...
def render_retrieval_flow(data: dict) -> str: ...
def render_failure_loop(data: dict) -> str: ...
def render_capability_map(data: dict) -> str: ...
def main() -> None: ...
```

Implementation requirements:

- Read `assets/diagrams/showcase-data.json` by default.
- Accept `--output-dir`.
- Use `viewBox="0 0 1600 900"` for every SVG.
- Use a white scientific canvas for the three RAGAS charts.
- Use dark navy, cyan, green, and orange for architecture and case-study diagrams.
- Add explicit legends for `historical`, `contaminated`, `upper_bound`, `formal`, and `current`.
- Shade L4-L6 with a neutral gray region.
- Label GT as `非端到端上限`.
- Label F2 as `当前综合最优`.
- Escape all user-visible XML text with `html.escape`.
- Write UTF-8 with a final newline.

- [ ] **Step 4: Generate the seven assets**

Run:

```powershell
python scripts/maintenance/generate_showcase_assets.py
```

Expected: seven SVG files under `assets/diagrams/`.

- [ ] **Step 5: Run tests and inspect the generated XML**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py -q
cd ..
git diff --check
```

Expected: all showcase tests pass and `git diff --check` has no output.

- [ ] **Step 6: Render visual previews**

Open each SVG in the in-app browser at full width. Capture PNG previews for:

- `assets/diagrams/previews/ragas-iteration-trend.png`
- `assets/diagrams/previews/threshold-comparison.png`
- `assets/diagrams/previews/rag-system-architecture.png`

Verify:

- no clipped labels;
- no overlapping legends;
- Chinese glyphs render;
- metrics remain readable at 50% scale;
- contaminated and formal runs are visually distinguishable without relying on color alone.

- [ ] **Step 7: Commit the asset generator**

```powershell
git add scripts/maintenance/generate_showcase_assets.py backend/tests/test_showcase_assets.py assets/diagrams
git commit -m "feat: generate interview showcase diagrams"
```

---

### Task 3: Reorganize Documentation Without Moving Runtime Code

**Files:**

- Move: files listed in the File Map
- Create: `docs/evaluation/README.md`
- Create: `docs/handoff/README.md`
- Create: `docs/archive/README.md`
- Modify: `docs/README.md`
- Modify: `docs/research/README.md`
- Modify: moved handoff and archive documents

- [ ] **Step 1: Capture the current Markdown reference inventory**

Run:

```powershell
rg -n "14\.06claude|CHATGPT_README|ragabilitytest|claude_memory|ragas_filter_experiment" -g "*.md" .
```

Expected: references from README, docs indexes, handoff records, and the approved design spec.

- [ ] **Step 2: Move tracked documents with Git**

Use `git mv` for every path in the File Map. Create destination directories first. Do not move Python files from `backend/`, and do not move JSON reports from `data/evaluations/`.

- [ ] **Step 3: Build the evaluation index**

`docs/evaluation/README.md` must contain:

```markdown
# Evaluation

## Current Baseline

F2 uses DeepSeek V4 Pro answers, MiMo v2.5 Pro judging, full generation contexts, and an adaptive cutoff ratio of 0.75.

| Faithfulness | Answer Relevancy | Context Precision |
|---:|---:|---:|
| 0.918 | 0.826 | 0.844 |

## Validity Classes

- **Formal:** F0-F3, generated and judged with complete contexts.
- **Historical:** L0-L3, useful for chronology but affected by configuration changes.
- **Upper bound:** GT, standard answers rather than end-to-end model responses.
- **Contaminated:** L4-L6, judged with truncated UI excerpts.

## Evidence

- [RAGAS report](ragas-report.md)
- [Iteration history](ragas-iteration-history.md)
- [Adaptive filtering experiment](adaptive-filter-experiment.md)
- [Raw reports](../../data/evaluations/reports/)
- [Evaluation datasets](../../data/evaluations/datasets/)
```

- [ ] **Step 4: Build handoff and archive indexes**

`docs/handoff/README.md` must identify the current handoff file and label the remaining records as historical. `docs/archive/README.md` must state that archived files are retained for traceability and may not reflect current implementation.

- [ ] **Step 5: Repair every relative Markdown link**

Update references found in Step 1, including the approved design spec. Preserve document content except for:

- path corrections;
- a one-line archive status banner;
- terminology corrections from “行业/企业标准线” to “项目目标线” when no source is cited.

- [ ] **Step 6: Confirm old paths are gone**

Run:

```powershell
rg -n "14\.06claude|CHATGPT_README|ragabilitytest|claude_memory" -g "*.md" .
```

Expected: no stale path references. Mentions that discuss historical folder names must be rewritten to current locations.

- [ ] **Step 7: Commit the documentation structure**

```powershell
git add docs data/evaluations/reports
git commit -m "docs: organize evaluation and handoff records"
```

---

### Task 4: Write the Architecture and Case-Study Narrative

**Files:**

- Create: `docs/architecture/system-architecture.md`
- Create: `docs/case-study/evaluation-integrity.md`
- Create: `docs/case-study/retrieval-and-prompt-debugging.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Document the current system architecture**

Write `docs/architecture/system-architecture.md` from the current implementation and cite these files:

- `backend/services/parser.py`
- `backend/services/recursive_chunker.py`
- `backend/services/hybrid_retriever.py`
- `backend/services/reranker.py`
- `backend/services/pipeline.py`
- `backend/services/generator.py`
- `backend/services/ragas_evaluator.py`

The document must distinguish:

- persistent ingestion from request-time retrieval;
- Vector Top-20 and BM25 Top-20 from final Top-3~5;
- full evaluation contexts from 200-character UI excerpts;
- online generation from offline RAGAS judging.

- [ ] **Step 2: Write the evaluation integrity case**

Use the six-part template from the design spec. Include the test evidence in:

- `backend/tests/test_evaluation_contexts.py`
- `backend/tests/test_maintenance_scripts.py`

State that L4-L6 are invalid for model-quality comparison because the Judge did not receive the same complete contexts used by generation.

- [ ] **Step 3: Write the retrieval and prompt debugging case**

Cover:

- Q00: answer correctness with Judge misclassification;
- Q02: evidence present but generation refused;
- why those require different fixes;
- why raising temperature was not the primary remedy;
- F0-F3 controlled experiment and the 0.75 decision;
- remaining Answer Relevancy variance caused by one generation being returned instead of three.

- [ ] **Step 4: Link the new documents from `docs/README.md`**

The index order must be:

1. Architecture
2. Evaluation
3. Case studies
4. API and operation
5. Handoff
6. Research and archive

- [ ] **Step 5: Review technical claims against code**

Run:

```powershell
rg -n "adaptive_cutoff_ratio|min_score|max_chunks_per_document|contexts|excerpt|top_k|20" backend/services backend/config.py backend/tests
```

Expected: every threshold, count, and context-channel claim in the new docs has a matching implementation or test reference.

- [ ] **Step 6: Commit the technical narrative**

```powershell
git add docs/architecture docs/case-study docs/README.md
git commit -m "docs: add architecture and debugging case studies"
```

---

### Task 5: Rebuild the Root README

**Files:**

- Modify: `README.md`
- Modify: `backend/tests/test_showcase_assets.py`

- [ ] **Step 1: Add failing README contract tests**

Append:

```python
def test_readme_embeds_core_showcase_assets():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = {
        "assets/diagrams/rag-system-architecture.svg",
        "assets/diagrams/ragas-iteration-trend.svg",
        "assets/diagrams/threshold-comparison.svg",
        "assets/diagrams/failure-analysis-loop.svg",
    }
    assert all(path in readme for path in required)


def test_readme_uses_careful_evaluation_language():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "当前端到端基线" in readme
    assert "项目目标线" in readme
    assert "行业标准线" not in readme
    assert "企业标准线" not in readme
    assert "受截断污染" in readme
```

- [ ] **Step 2: Verify the README tests fail**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py -q
```

Expected: FAIL because the current README does not embed the approved diagrams and still uses unsupported standard-line wording.

- [ ] **Step 3: Rewrite README in the approved order**

Use these exact top-level sections:

```markdown
# RAG Enterprise QA
## 当前端到端基线
## 从文档到可信回答
## 迭代不是一条漂亮的直线
## 为什么最终选择 0.75
## 两次最有价值的故障定位
## 工程能力地图
## 项目结构
## 快速开始
## 测试与评测
## 深入阅读
```

Required content:

- hero table with 0.918 / 0.826 / 0.844;
- project target lines clearly labeled as internal targets, not industry facts;
- architecture SVG immediately after the hero;
- iteration trend and threshold comparison in the evidence section;
- explicit warning that L4-L6 were contaminated;
- GT marked as non-end-to-end;
- links to architecture, evaluation, case study, API, and handoff indexes;
- unchanged backend setup and test commands;
- a warning that full RAGAS evaluation makes paid LLM calls;
- no exposed credentials or provider tokens.

- [ ] **Step 4: Run README contract tests**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py -q
```

Expected: all showcase tests pass.

- [ ] **Step 5: Visually inspect README**

Render README in a GitHub-like Markdown view and inspect desktop and narrow widths. Confirm:

- the hero communicates purpose and results without scrolling;
- no data table exceeds narrow width;
- diagrams retain readable labels;
- every image has useful alt text;
- no section repeats the same metric explanation.

- [ ] **Step 6: Commit the README**

```powershell
git add README.md backend/tests/test_showcase_assets.py
git commit -m "docs: present RAG project as an engineering case study"
```

---

### Task 6: Add Automated Showcase Validation

**Files:**

- Create: `scripts/maintenance/validate_showcase.py`
- Modify: `backend/tests/test_showcase_assets.py`

- [ ] **Step 1: Add a failing validator test**

Append:

```python
def test_showcase_validator_passes():
    script = ROOT / "scripts" / "maintenance" / "validate_showcase.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
```

- [ ] **Step 2: Verify the missing validator failure**

Run:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_showcase_assets.py::test_showcase_validator_passes -q
```

Expected: FAIL because the validator does not exist.

- [ ] **Step 3: Implement `validate_showcase.py`**

The standard-library validator must:

- scan all tracked Markdown files;
- resolve local Markdown links and image paths;
- ignore `http://`, `https://`, anchors, and fenced-code examples;
- verify all seven expected SVG files exist;
- verify generated SVG values match `showcase-data.json`;
- verify README contains the current F2 values;
- reject stale paths: `14.06claude写这里`, `CHATGPT_README.md`, `ragabilitytest.md`, and `claude_memory/`;
- print each failure and exit `1`;
- print `showcase validation passed` and exit `0` when clean.

- [ ] **Step 4: Run the validator and complete test suite**

Run:

```powershell
python scripts/maintenance/validate_showcase.py
cd backend
.\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests ablation_test.py
```

Expected:

- validator prints `showcase validation passed`;
- existing suite passes with at least the previous 48 tests plus the new showcase tests.

- [ ] **Step 5: Run final repository checks**

Run:

```powershell
cd ..
git diff --check
git status --short
git log --oneline -6
```

Expected:

- no whitespace errors;
- only intended files are modified or untracked;
- commits are separated by data, assets, docs, README, and validation.

- [ ] **Step 6: Commit validation**

```powershell
git add scripts/maintenance/validate_showcase.py backend/tests/test_showcase_assets.py
git commit -m "test: validate showcase links and assets"
```

- [ ] **Step 7: Push the completed work**

Run:

```powershell
git push origin main
```

Expected: `main` and `origin/main` point to the same final commit.

---

## Final Acceptance Checklist

- [ ] Seven diagrams are generated from one JSON source.
- [ ] Current baseline is 0.918 / 0.826 / 0.844 everywhere.
- [ ] L4-L6, GT, historical runs, and formal runs are visually distinct.
- [ ] README follows the approved A+C narrative with B-style data graphics.
- [ ] Runtime code locations and startup commands are unchanged.
- [ ] Documentation has clear architecture, evaluation, case-study, handoff, and archive entry points.
- [ ] All Markdown links and image references resolve.
- [ ] Existing and new tests pass.
- [ ] GitHub rendering is inspected before push.
- [ ] `origin/main` is synchronized.
