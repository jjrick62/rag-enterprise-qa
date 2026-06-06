from pathlib import Path


SHOWCASE_PATH = Path(__file__).resolve().parents[2] / "frontend" / "showcase.html"
GITHUB_URL = "https://github.com/jjrick62/rag-enterprise-qa"


def read_showcase() -> str:
    assert SHOWCASE_PATH.exists(), "frontend/showcase.html must exist"
    return SHOWCASE_PATH.read_text(encoding="utf-8")


def test_showcase_links_to_github_safely() -> None:
    html = read_showcase()

    assert GITHUB_URL in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html


def test_showcase_contains_current_f2_metrics() -> None:
    html = read_showcase()

    assert "0.918" in html
    assert "0.826" in html
    assert "0.844" in html


def test_showcase_labels_experiment_caveats() -> None:
    html = read_showcase()

    assert "L4-L6 受截断污染" in html
    assert "GT 非端到端上限" in html
    assert "0.75 综合最优" in html
    assert "行业标准" not in html
    assert "企业标准" not in html


def test_showcase_supports_mobile_and_reduced_motion() -> None:
    html = read_showcase()

    assert 'name="viewport"' in html
    assert "width=device-width" in html
    assert "prefers-reduced-motion" in html
