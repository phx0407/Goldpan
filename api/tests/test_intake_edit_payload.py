"""
api/tests/test_intake_edit_payload.py — DEC000001 §4/§5.2/§5.8/§7 item 5/§8
validation for intake.packet.edit_payload (CMD000033), Task #45.

Uses the same FastAPI TestClient + FakeSupabaseClient/dependency-override
pattern as api/tests/test_intake_claim_release.py and
api/tests/test_intake_review_decisions.py: FakeSupabaseClient
(api/tests/fake_supabase.py) stands in for a live Supabase connection, and a
directly-injected ActingUser stands in for a real X-User-Id lookup.
X-Admin-Key enforcement is overridden the same way and is out of scope here.

operations.edit_intake_packet_payload (supabase/migrations/019_intake_edit_
resubmit_reject_archive_rpcs.sql) is a single-transaction RPC that (1) locks
the packet row, (2) verifies returned-only state, (3) verifies Intake
Specialist ('canvasser') authority, (4) inserts the current packet_data into
operations.intake_packet_revisions.prior_payload, (5) updates packet_data to
the new payload, (6) inserts a cross-referenced 'annotate' event, (7) returns
the updated packet. FakeSupabaseClient.rpc(...)'s snapshot/restore rollback
simulation (see fake_supabase.py's module docstring) is what lets the
*_rolls_back_* tests below prove the packet/revision rows were never left
mid-transitioned, not merely that the HTTP response was an error.

No live database, no migration 019 execution — pure in-process behavior.
"""

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from api.deps import ActingUser, get_acting_user, get_supabase, verify_admin_key
from api.tests.conftest import app
from api.tests.fake_supabase import FakeDB, FakeSupabaseClient

SPECIALIST_1  = "55555555-5555-5555-5555-555555555555"   # Intake Specialist, edits in most tests
SPECIALIST_2  = "66666666-6666-6666-6666-666666666666"   # a different Intake Specialist
REVIEWER_A    = "11111111-1111-1111-1111-111111111111"   # Governance Reviewer — must be denied
ADMIN_1       = "33333333-3333-3333-3333-333333333333"   # Administrator — no override exists here
INACTIVE_1    = "77777777-7777-7777-7777-777777777777"   # seeded inactive

_ACTOR_DB_ROLE = {
    SPECIALIST_1: "canvasser",
    SPECIALIST_2: "canvasser",
    REVIEWER_A:   "reviewer",
    ADMIN_1:      "admin",
    INACTIVE_1:   "canvasser",
}


def _make_client(db: FakeDB, actor: Optional[ActingUser], actor_is_active: bool = True):
    app.dependency_overrides[get_supabase]     = lambda: FakeSupabaseClient(db)
    app.dependency_overrides[verify_admin_key] = lambda: "test-admin-key"
    if actor is not None:
        app.dependency_overrides[get_acting_user] = lambda: actor
        db.seed_user(
            user_id=actor.user_id,
            role=_ACTOR_DB_ROLE.get(actor.user_id, actor.role),
            is_active=actor_is_active,
        )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _seed_returned(db: FakeDB, **extra):
    fields = {
        "packet_status": "returned",
        "packet_data": {"restaurant": {"restaurant_name": "Original Name"}, "dishes": []},
        "return_reason": "missing evidence",
        "claimed_by_user_id": None,
        "claimed_at": None,
    }
    fields.update(extra)
    return db.seed_packet(**fields)


NEW_PAYLOAD = {"restaurant": {"restaurant_name": "Corrected Name"}, "dishes": [{"name": "Taco"}]}


def _edit(client: TestClient, packet_id: str = "pkt-1", packet_data=None, reason="fixed dish name"):
    return client.post(
        f"/admin/intake/{packet_id}/edit_payload",
        json={"packet_data": packet_data if packet_data is not None else NEW_PAYLOAD, "reason": reason},
    )


# ══════════════════════════════════════════════════════════════════════════
# 1. returned packet edit succeeds
# ══════════════════════════════════════════════════════════════════════════

def test_returned_packet_edit_succeeds():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = _edit(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "returned"  # unchanged — not a transition


# ══════════════════════════════════════════════════════════════════════════
# 2. prior payload is preserved exactly
# ══════════════════════════════════════════════════════════════════════════

def test_prior_payload_preserved_exactly():
    db = FakeDB()
    original = {"restaurant": {"restaurant_name": "Original Name"}, "dishes": [{"name": "Burger"}]}
    _seed_returned(db, packet_data=original)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = _edit(client, reason="correcting dish list")
    assert res.status_code == 200, res.text

    assert len(db.revisions) == 1
    rev = db.revisions[0]
    assert rev["prior_payload"] == original
    assert rev["actor_user_id"] == SPECIALIST_1
    assert rev["reason"] == "correcting dish list"


# ══════════════════════════════════════════════════════════════════════════
# 3. new payload is saved
# ══════════════════════════════════════════════════════════════════════════

def test_new_payload_is_saved():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = _edit(client, packet_data=NEW_PAYLOAD)
    assert res.status_code == 200, res.text
    assert db.packets[0]["packet_data"] == NEW_PAYLOAD

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "annotate"
    assert ev["actor_id"] == SPECIALIST_1
    assert ev["metadata"]["annotation_type"] == "payload_edit"
    assert ev["metadata"]["authority_basis"] == "intake_specialist"
    assert ev["metadata"]["actor_role"] == "canvasser"
    assert ev["metadata"]["revision_id"] == db.revisions[0]["revision_id"]


# ══════════════════════════════════════════════════════════════════════════
# 4. blank reason rejected
# ══════════════════════════════════════════════════════════════════════════

def test_blank_reason_rejected():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = _edit(client, reason="   ")
    assert res.status_code == 422
    assert db.packets[0]["packet_data"] == {"restaurant": {"restaurant_name": "Original Name"}, "dishes": []}
    assert db.revisions == []
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# 5. non-returned packet rejected
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("status_value", ["pending_review", "in_review", "approved", "rejected", "ingested"])
def test_non_returned_packet_rejected(status_value):
    db = FakeDB()
    db.seed_packet(packet_status=status_value, packet_data={"a": 1})
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = _edit(client)
    assert res.status_code == 409
    assert db.packets[0]["packet_data"] == {"a": 1}
    assert db.revisions == []
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# 6. Governance Reviewer denied
# ══════════════════════════════════════════════════════════════════════════

def test_governance_reviewer_denied():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer")
    client = _make_client(db, actor)

    res = _edit(client)
    assert res.status_code == 403
    assert db.packets[0]["packet_data"] == {"restaurant": {"restaurant_name": "Original Name"}, "dishes": []}
    assert db.revisions == []
    assert db.events == []


def test_administrator_denied_no_override_exists():
    """edit_payload has no admin override path — Administrator is not Intake Specialist."""
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = _edit(client)
    assert res.status_code == 403
    assert db.revisions == []
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# 7. inactive/invalid actor denied
# ══════════════════════════════════════════════════════════════════════════

def test_inactive_actor_denied():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=INACTIVE_1, role="canvasser", display_name="Inactive Specialist")
    client = _make_client(db, actor, actor_is_active=False)

    res = _edit(client)
    assert res.status_code == 403
    assert db.revisions == []
    assert db.events == []


def test_unknown_actor_denied():
    """Actor with no seeded operations.users row at all (never seeded)."""
    db = FakeDB()
    _seed_returned(db)
    unknown_id = "99999999-9999-9999-9999-999999999999"
    actor = ActingUser(user_id=unknown_id, role="canvasser", display_name="Ghost")
    app.dependency_overrides[get_supabase]     = lambda: FakeSupabaseClient(db)
    app.dependency_overrides[verify_admin_key] = lambda: "test-admin-key"
    app.dependency_overrides[get_acting_user]  = lambda: actor
    client = TestClient(app)

    res = _edit(client)
    assert res.status_code == 403
    assert db.revisions == []
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# 8. revision failure rolls back payload change
# ══════════════════════════════════════════════════════════════════════════

def test_revision_insert_failure_leaves_payload_untouched():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    _make_client(db, actor)
    db.simulate_revision_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = _edit(client)

    assert res.status_code == 500
    assert db.packets[0]["packet_data"] == {"restaurant": {"restaurant_name": "Original Name"}, "dishes": []}
    assert db.packets[0]["packet_status"] == "returned"
    assert db.revisions == []
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# 9. event failure rolls back both revision and payload change
# ══════════════════════════════════════════════════════════════════════════

def test_event_insert_failure_rolls_back_revision_and_payload():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    _make_client(db, actor)
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = _edit(client)

    assert res.status_code == 500
    # Neither side of the transaction committed:
    assert db.packets[0]["packet_data"] == {"restaurant": {"restaurant_name": "Original Name"}, "dishes": []}
    assert db.revisions == []
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# 10. multiple edits create an ordered append-only revision history
# ══════════════════════════════════════════════════════════════════════════

def test_multiple_edits_create_ordered_append_only_revision_history():
    db = FakeDB()
    v1 = {"restaurant": {"restaurant_name": "V1"}, "dishes": []}
    _seed_returned(db, packet_data=v1)
    actor1 = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist One")
    client = _make_client(db, actor1)

    v2 = {"restaurant": {"restaurant_name": "V2"}, "dishes": [{"name": "Soup"}]}
    res1 = _edit(client, packet_data=v2, reason="first correction")
    assert res1.status_code == 200, res1.text

    # A second, different Intake Specialist may also edit — packet stays 'returned'.
    db.seed_user(user_id=SPECIALIST_2, role="canvasser", is_active=True)
    app.dependency_overrides[get_acting_user] = lambda: ActingUser(
        user_id=SPECIALIST_2, role="canvasser", display_name="Specialist Two"
    )
    v3 = {"restaurant": {"restaurant_name": "V3"}, "dishes": [{"name": "Soup"}, {"name": "Salad"}]}
    res2 = client.post(
        "/admin/intake/pkt-1/edit_payload",
        json={"packet_data": v3, "reason": "second correction"},
    )
    assert res2.status_code == 200, res2.text

    assert db.packets[0]["packet_data"] == v3
    assert len(db.revisions) == 2
    # Append-only, ordered: revision 1 snapshots v1 (pre-first-edit), revision 2 snapshots v2 (pre-second-edit).
    assert db.revisions[0]["prior_payload"] == v1
    assert db.revisions[0]["actor_user_id"] == SPECIALIST_1
    assert db.revisions[0]["reason"] == "first correction"
    assert db.revisions[1]["prior_payload"] == v2
    assert db.revisions[1]["actor_user_id"] == SPECIALIST_2
    assert db.revisions[1]["reason"] == "second correction"
    # Neither revision was overwritten or deleted.
    assert db.revisions[0]["revision_id"] != db.revisions[1]["revision_id"]

    assert len(db.events) == 2
    assert [e["event_type"] for e in db.events] == ["annotate", "annotate"]
    assert db.events[0]["metadata"]["revision_id"] == db.revisions[0]["revision_id"]
    assert db.events[1]["metadata"]["revision_id"] == db.revisions[1]["revision_id"]
