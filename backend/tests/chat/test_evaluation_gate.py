import hashlib
import json
from pathlib import Path

from scripts.evaluate_explanations import _check_judgments
from scripts.render_explanation_review import _case_html


def test_answerable_case_cannot_pass_review_with_a_withheld_explanation(
    tmp_path: Path,
) -> None:
    capture = {
        "id": "e001",
        "turns": [{"answer": {"outcome": "validation_failed"}}],
    }
    captures = tmp_path / "captures.jsonl"
    captures.write_text(json.dumps(capture) + "\n")
    judgment = {
        "id": "e001",
        "answer_digest": hashlib.sha256(
            json.dumps(capture, sort_keys=True).encode()
        ).hexdigest(),
        "supported": True,
        "critical_status_error": False,
    }
    judgments = tmp_path / "judgments.jsonl"
    judgments.write_text(json.dumps(judgment) + "\n")
    dataset = {
        "cases": [
            {"id": "e001", "expected_paths": ["constitution-1999.chapter1.section1"]}
        ],
        "gates": {"supported_answer_judgment_minimum": 0.95},
    }

    failures = _check_judgments(dataset, judgments, captures)

    assert failures == ["e001: a withheld explanation cannot be marked supported"]


def test_review_page_disables_supported_for_withheld_answerable_case() -> None:
    case = {
        "id": "e001",
        "kind": "exact",
        "prompt": "Section 1",
        "expected_outcome": "supported",
        "expected_paths": ["constitution-1999.chapter1.section1"],
    }
    capture = {
        "id": "e001",
        "turns": [
            {
                "question": "Section 1",
                "answer": {"outcome": "validation_failed", "evidence": []},
            }
        ],
    }

    rendered = _case_html(case, capture)

    assert "Mark this case unsupported" in rendered
    assert "<option value='true' disabled>Yes</option>" in rendered
