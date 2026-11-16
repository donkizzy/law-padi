def test_unverified_account_cannot_claim_guest_history(guest_claim_account) -> None:
    guest, _stranger, _conversation_id, _user, headers = guest_claim_account
    assert guest.get("/api/v1/conversations", headers=headers).json()["count"] == 0
    unverified = guest.post("/api/v1/conversations/claim", headers=headers)
    assert unverified.status_code == 403


def test_verified_account_claims_guest_history(claimed_guest_conversation) -> None:
    guest, _stranger, conversation_id, headers, claimed = claimed_guest_conversation
    assert claimed.status_code == 200
    assert claimed.json()["claimed_count"] == 1
    assert (
        guest.get(
            f"/api/v1/conversations/{conversation_id}", headers=headers
        ).status_code
        == 200
    )


def test_claimed_history_is_no_longer_owned_by_guests(
    claimed_guest_conversation,
) -> None:
    guest, stranger, conversation_id, _headers, _claimed = claimed_guest_conversation
    assert guest.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
    assert stranger.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
