import hashlib
import json

from app.chat import EXPLANATION_PROMPT_VERSION
from scripts.evaluate_explanations import _check_captures, _check_judgments
from scripts.render_explanation_review import _case_html


def _capture() -> dict:
    text = "Everyone is entitled to privacy."
    evidence = {
        "evidence_id": "E1",
        "release_version": "release-1",
        "authoritative_text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "provision_version_id": "version-1",
        "canonical_path": "constitution.section37",
        "citation": "Section 37",
        "source_document_id": "source-1",
        "source_title": "Constitution",
        "source_content_url": "/source.pdf",
    }
    return {
        "id": "e001",
        "release_version": "release-1",
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "build_revision": "source-test",
        "retrieval_mode": "lexical",
        "retrieval_mode_source": "inline_worker_settings",
        "turns": [
            {
                "question": "Section 37",
                "retrieval_mode": "exact",
                "answer": {
                    "outcome": "completed",
                    "evidence": [evidence],
                    "blocks": [
                        {
                            "text": "The provision protects privacy.",
                            "evidence_ids": ["E1"],
                            "quotation": "entitled to privacy",
                        }
                    ],
                },
            }
        ],
    }


def test_review_capture_checks_provenance_and_block_references(tmp_path):
    dataset = {
        "release_version": "release-1",
        "cases": [
            {
                "id": "e001",
                "kind": "exact",
                "turns": ["Section 37"],
                "expected_paths": ["constitution.section37"],
            }
        ],
    }
    path = tmp_path / "captures.jsonl"
    capture = _capture()
    path.write_text(json.dumps(capture) + "\n")
    assert (
        _check_captures(
            dataset,
            path,
            expected_build_revision="source-test",
            expected_retrieval_mode="lexical",
        )
        == []
    )

    capture["turns"][0]["answer"]["evidence"][0]["authoritative_text"] = "Altered"
    path.write_text(json.dumps(capture) + "\n")
    assert "e001: evidence provenance mismatch" in _check_captures(
        dataset,
        path,
        expected_build_revision="source-test",
        expected_retrieval_mode="lexical",
    )


def test_review_requires_explicit_human_judgments(tmp_path):
    dataset = {
        "cases": [{"id": "e001"}],
        "gates": {"supported_answer_judgment_minimum": 0.95},
    }
    path = tmp_path / "judgments.jsonl"
    path.write_text('{"id":"e001","supported":true}\n')
    assert "A critical legal-status error was reported" in _check_judgments(
        dataset, path
    )

    captures = tmp_path / "captures.jsonl"
    captures.write_text(json.dumps(_capture()) + "\n")
    path.write_text(
        '{"id":"e001","supported":true,"critical_status_error":false,'
        '"answer_digest":"stale"}\n'
    )
    assert "e001: judgment does not match captured answer" in _check_judgments(
        dataset, path, captures
    )


def test_review_rejects_answer_to_a_different_question(tmp_path):
    dataset = {
        "release_version": "release-1",
        "cases": [
            {
                "id": "e001",
                "kind": "exact",
                "turns": ["Section 37"],
                "expected_paths": ["constitution.section37"],
            }
        ],
    }
    capture = _capture()
    capture["turns"][0]["question"] = "What does section 38 say?"
    path = tmp_path / "captures.jsonl"
    path.write_text(json.dumps(capture) + "\n")
    assert "e001: captured questions differ from dataset" in _check_captures(
        dataset,
        path,
        expected_build_revision="source-test",
        expected_retrieval_mode="lexical",
    )


def test_review_page_escapes_model_text():
    capture = _capture()
    capture["turns"][0]["answer"]["blocks"][0]["text"] = "<script>alert(1)</script>"
    page = _case_html(
        {
            "id": "e001",
            "kind": "exact",
            "prompt": "Section 37",
            "expected_outcome": "supported",
        },
        capture,
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page
