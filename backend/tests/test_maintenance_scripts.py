import ast
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script_name", ["gen_answers.py"])
def test_evaluation_scripts_do_not_truncate_qa_pairs(script_name):
    tree = ast.parse(
        (BACKEND_DIR / script_name).read_text(encoding="utf-8"),
        filename=script_name,
    )

    truncated_qa_pairs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "qa_pairs"
        and isinstance(node.slice, ast.Slice)
    ]

    assert truncated_qa_pairs == []


def test_llm_factory_does_not_hardcode_api_keys():
    source = (BACKEND_DIR / "services" / "llm_factory.py").read_text(
        encoding="utf-8"
    )

    assert "ghp_" not in source
    assert "sk-" not in source
    assert "MIMO_API_KEY" in source


def test_backend_runtime_has_no_deepseek_references():
    runtime_files = [
        path
        for path in BACKEND_DIR.rglob("*.py")
        if not any(part.startswith("venv") for part in path.parts)
        and "__pycache__" not in path.parts
        and "tests" not in path.parts
    ]
    runtime_files.append(BACKEND_DIR / ".env.example")

    offenders = []
    for path in runtime_files:
        source = path.read_text(encoding="utf-8").lower()
        if "deepseek" in source:
            offenders.append(str(path.relative_to(BACKEND_DIR)))

    assert offenders == []
