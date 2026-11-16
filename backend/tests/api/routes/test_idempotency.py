def test_repeated_message_returns_the_same_run(submitted_guest_message) -> None:
    guest, _stranger, conversation_id, first, message = submitted_guest_message
    assert first.status_code == 202
    second = guest.post(
        f"/api/v1/conversations/{conversation_id}/messages", json=message
    )
    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]


def test_idempotency_key_rejects_a_different_question(submitted_guest_message) -> None:
    guest, _stranger, conversation_id, _first, _message = submitted_guest_message
    assert (
        guest.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": "Section 33", "idempotency_key": "once"},
        ).status_code
        == 409
    )


def test_pending_run_blocks_a_second_message(submitted_guest_message) -> None:
    guest, _stranger, conversation_id, _first, _message = submitted_guest_message
    assert (
        guest.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"question": "Section 33", "idempotency_key": "twice"},
        ).status_code
        == 409
    )
