import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "assets" / "diagrams" / "showcase-data.json"


def load_data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_f2_is_the_current_baseline_with_expected_scores():
    data = load_data()
    f2 = next(item for item in data["iterations"] if item["id"] == "F2")

    assert f2 == {
        "id": "F2",
        "faithfulness": 0.918,
        "answer_relevancy": 0.826,
        "context_precision": 0.844,
        "status": "current",
    }


def test_gt_is_an_upper_bound_and_l4_through_l6_are_contaminated():
    data = load_data()
    iterations = {item["id"]: item for item in data["iterations"]}

    assert iterations["GT"]["status"] == "upper_bound"
    assert all(iterations[item_id]["status"] == "contaminated" for item_id in ("L4", "L5", "L6"))


def test_threshold_selection_and_metric_tradeoff_are_locked():
    data = load_data()
    thresholds = {item["threshold"]: item for item in data["thresholds"]}

    assert thresholds["0.75"]["selected"] is True
    assert thresholds["0.75"]["mean"] == 0.863
    assert thresholds["0.80"]["faithfulness"] > thresholds["0.75"]["faithfulness"]
    assert thresholds["0.80"]["answer_relevancy"] < thresholds["0.75"]["answer_relevancy"]
