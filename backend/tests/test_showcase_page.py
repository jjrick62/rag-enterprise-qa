import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable


SHOWCASE_PATH = Path(__file__).resolve().parents[2] / "frontend" / "showcase.html"
SHOWCASE_DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "diagrams"
    / "showcase-data.json"
)
GITHUB_URL = "https://github.com/jjrick62/rag-enterprise-qa"
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


@dataclass
class Element:
    tag: str
    attrs: dict[str, str | None]
    parent: "Element | None" = None
    children: list["Element"] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        parts = [*self.text_parts, *(child.text for child in self.children)]
        return " ".join(" ".join(parts).split())

    def has_class(self, class_name: str) -> bool:
        return class_name in (self.attrs.get("class") or "").split()

    def descendants(self, tag: str | None = None) -> list["Element"]:
        matches: list[Element] = []
        for child in self.children:
            if tag is None or child.tag == tag:
                matches.append(child)
            matches.extend(child.descendants(tag))
        return matches


class ShowcaseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = Element("document", {})
        self.stack = [self.root]

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        element = Element(tag, dict(attrs), parent=self.stack[-1])
        self.stack[-1].children.append(element)
        if tag not in VOID_ELEMENTS:
            self.stack.append(element)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].text_parts.append(data)


def read_showcase() -> str:
    assert SHOWCASE_PATH.exists(), "frontend/showcase.html must exist"
    return SHOWCASE_PATH.read_text(encoding="utf-8")


def parse_showcase() -> Element:
    parser = ShowcaseParser()
    parser.feed(read_showcase())
    return parser.root


def find_one(
    root: Element,
    tag: str,
    predicate: Callable[[Element], bool] = lambda _element: True,
) -> Element:
    matches = [element for element in root.descendants(tag) if predicate(element)]
    assert len(matches) == 1, f"expected one matching <{tag}>, found {len(matches)}"
    return matches[0]


def test_showcase_links_to_github_safely() -> None:
    document = parse_showcase()
    github_links = [
        link
        for link in document.descendants("a")
        if link.attrs.get("href") == GITHUB_URL
    ]

    assert len(github_links) >= 2
    for link in github_links:
        assert link.attrs.get("target") == "_blank"
        assert {"noopener", "noreferrer"} <= set(
            (link.attrs.get("rel") or "").split()
        )

    hero = find_one(document, "header", lambda node: node.attrs.get("id") == "top")
    footer = find_one(document, "footer")
    assert any(link.text == "VIEW ON GITHUB" for link in hero.descendants("a"))
    assert any(link.text == "VIEW ON GITHUB" for link in footer.descendants("a"))


def test_showcase_hero_contract() -> None:
    document = parse_showcase()
    hero = find_one(document, "header", lambda node: node.attrs.get("id") == "top")

    assert find_one(hero, "h1").text == "RAG Enterprise QA"
    assert "端到端企业文档问答" in hero.text
    assert any(link.text == "VIEW ON GITHUB" for link in hero.descendants("a"))
    assert any(
        link.attrs.get("href") == "#benchmark" and link.text == "向下浏览"
        for link in hero.descendants("a")
    )
    for detail in (
        "30 道 watsonxDocsQA",
        "DeepSeek V4 Pro",
        "MiMo v2.5 Pro",
        "完整上下文",
    ):
        assert detail in hero.text


def test_showcase_contains_complete_architecture_pipeline() -> None:
    document = parse_showcase()
    architecture = find_one(
        document, "section", lambda node: node.attrs.get("id") == "architecture"
    )
    stage_titles = [
        title.text
        for stage in architecture.descendants("div")
        if stage.has_class("stage")
        for title in stage.descendants("strong")
    ]

    assert stage_titles == [
        "Document Parse",
        "Recursive Chunk",
        "Vector Top-20 + BM25 Top-20",
        "RRF",
        "BGE Reranker",
        "Evidence Gate",
        "Top-3~5 Full Chunks",
        "LLM Streaming Answer",
        "Full-context RAGAS",
        "Traceable Output",
    ]
    for detail in ("absolute 0.50", "per-doc max 4", "relative 0.75"):
        assert detail in architecture.text


def test_showcase_contains_failure_dossiers() -> None:
    document = parse_showcase()
    cases = find_one(
        document, "section", lambda node: node.attrs.get("id") == "cases"
    )
    case_studies = [
        article
        for article in cases.descendants("article")
        if article.attrs.get("data-case-study")
    ]

    assert [case.attrs["data-case-study"] for case in case_studies] == [
        "ragas-truncation",
        "q00-q02-attribution",
    ]

    truncation_case, attribution_case = case_studies
    assert "RAGAS 截断漏洞" in truncation_case.text
    assert "200 字摘要" in truncation_case.text
    assert [term.text for term in truncation_case.descendants("dt")] == [
        "现象",
        "证据",
        "根因",
        "修复",
    ]

    assert "Q00" in attribution_case.text
    assert "Q02" in attribution_case.text
    assert "JUDGE FALSE NEGATIVE" in attribution_case.text
    assert "PROMPT OVER-CONSTRAINT" in attribution_case.text
    assert "Judge 对表述差异过敏" in attribution_case.text
    assert "Prompt 对“完全明确”的要求过严" in attribution_case.text


def test_showcase_contains_four_capability_quadrants() -> None:
    document = parse_showcase()
    capabilities = find_one(
        document, "section", lambda node: node.attrs.get("id") == "capabilities"
    )
    quadrant_titles = [
        heading.text
        for quadrant in capabilities.descendants("article")
        if quadrant.has_class("quadrant")
        for heading in quadrant.descendants("h3")
    ]

    assert quadrant_titles == ["算法", "后端", "评测", "产品"]


def test_showcase_footer_displays_repository_url() -> None:
    document = parse_showcase()
    footer = find_one(document, "footer")
    url_link = find_one(footer, "a", lambda node: node.has_class("footer-url"))

    assert url_link.attrs.get("href") == GITHUB_URL
    assert url_link.text == GITHUB_URL


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


def test_showcase_scroll_regions_are_contained_by_their_layout() -> None:
    html = read_showcase()

    assert re.search(
        r"\.scroll-region\s*\{"
        r"(?=[^}]*\bmin-width:\s*0)"
        r"(?=[^}]*\bwidth:\s*100%)"
        r"(?=[^}]*\bmax-width:\s*100%)"
        r"(?=[^}]*\boverflow-x:\s*auto)",
        html,
        re.DOTALL,
    )


def test_showcase_embeds_canonical_data_as_json() -> None:
    document = parse_showcase()
    data_script = find_one(
        document,
        "script",
        lambda node: node.attrs.get("id") == "showcase-data",
    )

    assert data_script.attrs.get("type") == "application/json"
    assert json.loads(data_script.text) == json.loads(
        SHOWCASE_DATA_PATH.read_text(encoding="utf-8")
    )

    html = read_showcase()
    assert 'JSON.parse(document.getElementById("showcase-data").textContent)' in html


def test_showcase_reveals_are_visible_without_javascript() -> None:
    html = read_showcase()

    assert re.search(r"\.reveal\s*\{[^}]*opacity:\s*1", html, re.DOTALL)
    assert re.search(
        r"\.js\s+\.reveal\s*\{[^}]*opacity:\s*0",
        html,
        re.DOTALL,
    )
    assert ".js .reveal.is-visible" in html


def test_showcase_threshold_table_contains_four_static_rows() -> None:
    document = parse_showcase()
    threshold_body = find_one(
        document,
        "tbody",
        lambda node: node.attrs.get("id") == "threshold-body",
    )
    rows = threshold_body.descendants("tr")

    assert len(rows) == 4
    assert [row.descendants("td")[0].text for row in rows] == [
        "off",
        "0.70",
        "0.75",
        "0.80",
    ]


def test_showcase_uses_semantic_iteration_lookup() -> None:
    html = read_showcase()

    assert not re.search(r"iterations\s*\[\s*(?:4|10)\s*\]", html)
    assert ".find(" in html
    assert 'status === "contaminated"' in html
    assert 'item.id === "GT"' in html
    assert 'status === "upper_bound"' in html
    assert "current_baseline" in html
    assert 'status === "current"' in html


def test_showcase_exposes_all_iteration_metrics_accessibly() -> None:
    document = parse_showcase()
    summary = find_one(
        document,
        "table",
        lambda node: node.attrs.get("id") == "iteration-data-summary",
    )
    assert not summary.has_class("visually-hidden")
    assert summary.parent is not None
    assert summary.parent.tag != "table"
    assert summary.parent.has_class("visually-hidden")
    assert find_one(summary, "caption").text

    rows = summary.descendants("tbody")[0].descendants("tr")

    assert len(rows) == 12
    for row in rows:
        cells = row.descendants("td")
        assert len(cells) == 5
        assert cells[0].text
        assert all(cells[index].text for index in (1, 2, 3))
        assert cells[4].text

    scroll_regions = [
        node
        for node in document.descendants("div")
        if node.has_class("scroll-region")
    ]
    assert len(scroll_regions) >= 2
    for region in scroll_regions:
        assert region.attrs.get("tabindex") == "0"
        assert region.attrs.get("aria-label")

    html = read_showcase()
    assert "stroke-dasharray" in html
    assert all(shape in html for shape in ('shape: "circle"', 'shape: "square"', 'shape: "diamond"'))
