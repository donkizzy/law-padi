"""Run with unittest, not the destructive database-backed pytest fixtures."""

import copy
import unittest
from unittest.mock import patch

from sqlalchemy.engine import Engine

from app.legal.enums import PageRole

# Imports may construct an engine, but this suite forbids opening a connection.
with patch.object(Engine, "connect", side_effect=AssertionError("No database access")):
    from scripts.stage_statute_review import page_role_proposals, stage_source


class PageRoleProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection_guard = patch.object(
            Engine, "connect", side_effect=AssertionError("No database access")
        )
        self.connection_guard.start()
        self.addCleanup(self.connection_guard.stop)

    def test_explicit_roles_preserve_mixed_case_ocr_and_distinguish_back_matter(
        self,
    ) -> None:
        pages = [
            {
                "page_number": 5,
                "text": "EnACted by the National Assembly",
                "role": "legal_body",
                "role_reason": "Proposed body opening on the source image",
            },
            {
                "page_number": 24,
                "text": "First Schedule",
                "role": "schedule",
                "role_reason": "Principal schedule",
            },
            {
                "page_number": 30,
                "text": "I ASSENT",
                "role": "back_matter",
                "role_reason": "Assent evidence only",
            },
        ]
        original = copy.deepcopy(pages)
        result = page_role_proposals(pages)
        self.assertEqual(pages, original)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result[5][0], PageRole.LEGAL_BODY)
        self.assertEqual(result[24][0], PageRole.SCHEDULE)
        self.assertEqual(result[30], (PageRole.BACK_MATTER, "Assent evidence only"))

    def test_legacy_payload_stays_legacy(self) -> None:
        self.assertIsNone(page_role_proposals([{"page_number": 1, "text": "OCR"}]))

    def test_partial_invalid_and_unreasoned_roles_fail(self) -> None:
        valid = {"page_number": 1, "role": "front_matter", "role_reason": "Cover"}
        for invalid in (
            {"page_number": 2},
            {"page_number": 2, "role": "unknown", "role_reason": "Evidence"},
            {"page_number": 2, "role": "schedule", "role_reason": "  "},
            {"page_number": 2, "role": "schedule", "role_reason": None},
            {"page_number": 2, "role_reason": "Missing role"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                page_role_proposals([valid, invalid])

    def test_duplicate_role_pages_fail(self) -> None:
        page = {"page_number": 1, "role": "front_matter", "role_reason": "Cover"}
        with self.assertRaises(ValueError):
            page_role_proposals([page, page.copy()])

    def test_invalid_roles_fail_before_session_access(self) -> None:
        from types import SimpleNamespace

        from app.legal.enums import InstrumentType

        source = SimpleNamespace(sha256="a" * 64, page_count=1)
        instrument = SimpleNamespace(instrument_type=InstrumentType.ACT)
        payload = {
            "source_sha256": source.sha256,
            "pages": [{"page_number": 1, "role": "legal_body"}],
        }
        from app.core.config import settings

        with (
            patch.object(
                settings,
                "INGESTION_ALLOWED_INSTRUMENT_TYPES",
                ["constitution", "act"],
            ),
            self.assertRaisesRegex(ValueError, "role reason"),
        ):
            # No Session object is provided: accessing it would fail the test.
            stage_source(None, source, instrument, payload, "b" * 64)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
