from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from app.chat import history
from app.legal.enums import MessageRole
from app.legal.models import ConversationMessage, get_datetime_utc


def test_history_preserves_distinct_time_bounds_and_loads_prior_answer_once(
    guest_conversation, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _guest, _stranger, _created, identity = guest_conversation
    conversation_id = UUID(identity)
    now = get_datetime_utc()
    earlier = ConversationMessage(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Earlier question",
        created_at=now - timedelta(seconds=1),
    )
    current = ConversationMessage(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Why?",
        created_at=now,
    )
    later = ConversationMessage(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Later question",
        created_at=now + timedelta(seconds=2),
    )
    assistant = ConversationMessage(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="Privacy",
        created_at=now + timedelta(seconds=1),
        answer_content={"blocks": [{"evidence_ids": ["E1"]}]},
        evidence_snapshot=[
            {
                "evidence_id": "E1",
                "citation": "Section 37",
                "canonical_path": "constitution-1999.chapter4.section37",
            }
        ],
    )
    db.add_all([earlier, current, later, assistant])
    db.commit()
    queries = 0
    load = history.load_prior_answer

    def counted(session: Session, identity: UUID) -> ConversationMessage | None:
        nonlocal queries
        queries += 1
        return load(session, identity)

    monkeypatch.setattr(history, "load_prior_answer", counted)
    window = history.History(db, conversation_id, current)
    assert window.context == [{"role": "user", "question": "Earlier question"}]
    assert window.previous_question == "Later question"
    assert history.relative_query(db, conversation_id, "Why?", window) == "Section 37"
    assert history.prior_citations(db, conversation_id, window) == ["Section 37"]
    assert history.prior_section_path(db, conversation_id, window) == (
        "constitution-1999.chapter4.section37"
    )
    assert queries == 1


@pytest.mark.parametrize("resolved", [False, True])
def test_prior_citation_and_path_fallback_rules_remain_distinct(
    db: Session, monkeypatch: pytest.MonkeyPatch, resolved: bool
) -> None:
    message = ConversationMessage(
        conversation_id=uuid4(),
        role=MessageRole.ASSISTANT,
        content="",
        answer_content={
            "citation_outcomes": [
                {
                    "status": "resolved" if resolved else "missing",
                    "evidence_ids": ["E1"],
                }
            ]
        },
        evidence_snapshot=[
            {
                "evidence_id": "E1",
                "citation": "Section 37",
                "canonical_path": "constitution-1999.chapter4.section37",
            }
        ],
    )
    monkeypatch.setattr(history, "load_prior_answer", lambda *_: message)
    assert history.prior_citations(db, message.conversation_id) == (
        ["Section 37"] if resolved else []
    )
    assert history.prior_section_path(db, message.conversation_id) == (
        "constitution-1999.chapter4.section37" if resolved else None
    )


@pytest.mark.parametrize(
    "question",
    [
        "Why?",
        "What does it mean?",
        "What exceptions apply?",
        "What limitations apply?",
        "What about subsection 2?",
        "And paragraph (b)?",
        "What about the next section?",
        "Explain that more simply",
        "What qualifications or exceptions does that section contain?",
        "Does it apply to foreigners?",
        "Is it legal?",
        "Tell me more",
        "Give me an example",
    ],
)
def test_a_question_without_a_subject_of_its_own_is_a_followup(question: str) -> None:
    assert history.is_followup_question(question)


@pytest.mark.parametrize(
    "question",
    [
        "How long can police detain me?",
        "Is it legal to record a police officer?",
        "How do I apply for bail?",
        "Why was I arrested?",
        "What about freedom of religion?",
        "How can I enforce this right?",
        "Why do police need a warrant to search my house?",
        "Is it true that police can detain me for 48 hours?",
        "Can police search my phone?",
    ],
)
def test_pronouns_and_why_or_how_do_not_make_a_new_question_a_followup(
    question: str,
) -> None:
    assert not history.is_followup_question(question)


@pytest.mark.parametrize("question", ["Tell me more", "Give me an example"])
def test_a_question_with_no_subject_words_reuses_the_discussed_sections(
    db: Session, monkeypatch: pytest.MonkeyPatch, question: str
) -> None:
    monkeypatch.setattr(history, "prior_citations", lambda *_: ["Section 37"])
    assert history.relative_query(db, uuid4(), question) == "Section 37"
    monkeypatch.setattr(
        history, "prior_citations", lambda *_: ["Section 37", "Section 33"]
    )
    assert history.relative_query(db, uuid4(), question) == (
        "Section 37 and Section 33"
    )
