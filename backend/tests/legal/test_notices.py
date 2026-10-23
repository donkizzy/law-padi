from app.legal.notices import provision_notices
from app.legal.schemas import EvidenceItem, ProvisionReference


def test_section_120_carries_repeated_text_notice() -> None:
    notices = provision_notices("acja-2015.part15.section120")
    assert [n.code for n in notices] == ["repeats_other_provision"]
    assert notices[0].params == {
        "repeated": "121",
        "section": "120",
        "heading": "Discretion in ex parte application",
    }
    assert "section 121" in notices[0].text


def test_notice_applies_beneath_its_provision_only() -> None:
    assert provision_notices("acja-2015.schedule1.item8.paragrapha")
    assert provision_notices("acja-2015.schedule1.item9")
    # A path that merely shares a prefix is a different provision.
    assert provision_notices("acja-2015.schedule1.item80") == []
    assert provision_notices("acja-2015.part15.section121") == []
    assert provision_notices("constitution-1999.chapter4.section37") == []


def test_every_notice_names_a_translatable_code() -> None:
    for path in (
        "acja-2015.part15.section120",
        "acja-2015.schedule1.item8",
        "acja-2015.schedule1.item9",
    ):
        for notice in provision_notices(path):
            assert notice.code in {
                "repeats_other_provision",
                "missing_page_secondary_source",
            }
            assert notice.text


def test_public_shapes_default_to_no_notices() -> None:
    # Saved evidence snapshots predate notices and must still load.
    assert "notices" in EvidenceItem.model_fields
    assert ProvisionReference.model_fields["notices"].default_factory() == []
