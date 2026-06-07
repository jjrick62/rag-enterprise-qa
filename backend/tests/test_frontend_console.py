from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "index.html"
CSS = ROOT / "frontend" / "css" / "style.css"
CHAT_JS = ROOT / "frontend" / "js" / "chat.js"


def test_console_has_three_column_trust_layout():
    html = INDEX.read_text(encoding="utf-8")

    assert 'class="console-rail"' in html
    assert 'class="chat-workspace"' in html
    assert 'class="evidence-panel"' in html
    assert 'id="evidence-list"' in html


def test_console_exposes_pipeline_and_quality_signals():
    html = INDEX.read_text(encoding="utf-8")

    for stage in (
        "Query Rewrite",
        "Vector + BM25",
        "RRF Fusion",
        "BGE Rerank",
        "Adaptive Filter",
        "LLM Answer",
    ):
        assert stage in html

    for metric in ("0.931", "0.857", "Faithfulness", "Answer Relevancy", "Context Precision"):
        assert metric in html


def test_console_css_defines_desktop_and_mobile_layouts():
    css = CSS.read_text(encoding="utf-8")

    assert "grid-template-columns: 72px minmax(0, 1fr) 320px" in css
    assert "@media (max-width: 1080px)" in css
    assert "@media (max-width: 760px)" in css


def test_chat_updates_pipeline_and_evidence_panel():
    script = CHAT_JS.read_text(encoding="utf-8")

    assert "_setPipelineState" in script
    assert "_renderEvidencePanel" in script
    assert "evidence-list" in script
