from app.ingestion.worker import (
    _normalize_page_text,
)


def test_normalize_page_text_rejoins_split_section_markers() -> None:
    assert (
        _normalize_page_text(
            "Chapter I\n1\n. (1) This Constitution is supreme.\n1\n2. Twelfth item"
        )
        == "Chapter I\n1. (1) This Constitution is supreme.\n12. Twelfth item"
    )
