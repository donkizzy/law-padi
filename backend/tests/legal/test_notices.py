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


def test_minimum_wage_section_3_warns_of_the_2024_amendment() -> None:
    path = "national-minimum-wage-act-2019.section3"
    for target in (path, f"{path}.subsection1"):
        notices = provision_notices(target)
        assert [n.code for n in notices] == ["minimum_wage_amended_2024"]
        assert "₦70,000" in notices[0].text
    assert provision_notices("national-minimum-wage-act-2019.section4") == []


def test_cybercrimes_sections_warn_of_later_amendments() -> None:
    root = "cybercrimes-prohibition-prevention-etc-act-2015"
    levy = provision_notices(f"{root}.part5.section44.subsection2")
    assert [n.code for n in levy] == ["cybercrimes_s44_amended"]
    assert "Nigeria Tax Act 2025" in levy[0].text
    stalking = provision_notices(f"{root}.part3.section24")
    assert [n.code for n in stalking] == ["cybercrimes_s24_amended_2024"]
    assert [n.code for n in provision_notices(f"{root}.schedule2")] == [
        "cybercrimes_second_schedule_deleted"
    ]
    assert provision_notices(f"{root}.part3.section25") == []


def test_penal_code_marks_the_sections_missing_from_its_only_copy() -> None:
    root = "penal-code-act-abuja.code"
    for path, code in (
        (f"{root}.chapterxiii.section196", "penal_code_gap_197_212"),
        (f"{root}.chapterxvi.section213", "penal_code_gap_197_212"),
        (f"{root}.chapterxx.section363", "penal_code_gap_364_365"),
        (f"{root}.chapterxx.section366", "penal_code_gap_364_365"),
        (f"{root}.chapterxxv.section409", "penal_code_gap_410_477"),
        (f"{root}.chapterxxii.section384", "penal_code_s384_penalty_lost"),
    ):
        assert [n.code for n in provision_notices(path)] == [code]
    assert provision_notices(f"{root}.chapterxx.section367") == []


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
