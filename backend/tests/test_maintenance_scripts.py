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


def test_q02_trace_uses_current_prompt_and_generator_signatures():
    tree = ast.parse(
        (BACKEND_DIR / "_trace_q02.py").read_text(encoding="utf-8"),
        filename="_trace_q02.py",
    )
    calls = list(ast.walk(tree))

    context_calls = [
        node
        for node in calls
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_context_block"
    ]
    generator_calls = [
        node
        for node in calls
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "generator"
        and node.func.attr == "generate"
    ]

    assert len(context_calls) == 1
    assert len(context_calls[0].args) == 1
    assert isinstance(context_calls[0].args[0], ast.Name)
    assert context_calls[0].args[0].id == "reranked"

    assert len(generator_calls) == 1
    assert len(generator_calls[0].args) == 2
    assert isinstance(generator_calls[0].args[1], ast.Name)
    assert generator_calls[0].args[1].id == "reranked"


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
