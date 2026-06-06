import ast
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script_name", ["gen_answers.py", "run_ragas_eval.py"])
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


def test_reingest_script_clears_retriever_without_deleting_database_directory():
    source = (BACKEND_DIR / "_reingest.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="_reingest.py")

    method_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]

    assert not any(node.func.attr == "rmtree" for node in method_calls)
    assert any(node.func.attr == "clear" for node in method_calls)


def test_llm_factory_does_not_hardcode_api_keys():
    source = (BACKEND_DIR / "services" / "llm_factory.py").read_text(
        encoding="utf-8"
    )

    assert "ghp_" not in source
    assert "sk-" not in source
    assert "MIMO_API_KEY" in source
    assert "DEEPSEEK_API_KEY" in source
