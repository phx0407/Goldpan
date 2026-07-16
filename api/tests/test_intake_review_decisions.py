"""
api/tests/test_intake_review_decisions.py — DEC000001 §5.5/§5.9 validation
for intake.review.approve (CMD000005) and intake.review.return (CMD000006),
task #44 (corrected for transactional integrity).

Uses FastAPI's TestClient against the real app/router wiring, with
dependency overrides swapping in a FakeSupabaseClient (api/tests/fake_supabase.py)
in place of a live Supabase connection, and a directly-injected ActingUser in
place of a real X-User-Id lookup. X-Admin-Key enforcement itself is exercised
implicitly (verify_admin_key is overridden so the transport-layer header
check is not what's under test here — that mechanism is covered by its own
unit behavior in api/deps.py and is out of scope for this file, which
targets the claim/decision authorization logic added in task #44).

approve_packet()/return_packet() now call a single Postgres RPC each
(operations.approve_intake_packet / operations.return_intake_packet,
supabase/migrations/017_intake_review_decision_rpcs.sql) instead of a
SELECT + conditional UPDATE + separate INSERT. FakeSupabaseClient.rpc(...)
(api/tests/fake_supabase.py) emulates those functions' logic, including
genuine snapshot/restore rollback if the fake implementation raises — this
is what lets test_*_failed_event_insert_does_not_report_success below prove
the packet row was never left mid-transitioned, not merely that the HTTP
response was an error.

No live database, no migration 016/017 execution — pure in-process behavior.
"""

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from api.deps import ActingUser, get_acting_user, get_supabase, verify_admin_key
from api.tests.conftest import app
from api.tests.fake_supabase import FakeDB, FakeSupabaseClient

REVIEWER_A = "11111111-1111-1111-1111-111111111111"   # claimant in most tests
REVIEWER_B = "22222222-2222-2222-2222-222222222222"   # a different Governance Reviewer
ADMIN_1    = "33333333-3333-3333-3333-333333333333"

# DB role backing each constant above, used to auto-seed FakeDB's "users"
# table so the fake decision RPCs' admin-override role lookup (mirroring
# operations.approve_intake_packet's own `SELECT role FROM operations.users`)
# resolves the way each test expects.
_ACTOR_DB_ROLE = {
    REVIEWER_A: "reviewer",
    REVIEWER_B: "reviewer",
    ADMIN_1:    "admin",
}


def _make_client(db: FakeDB, actor: Optional[ActingUser]):
    app.dependency_overrides[get_supabase]     = lambda: FakeSupabaseClient(db)
    app.dependency_overrides[verify_admin_key] = lambda: "test-admin-key"
    if actor is not None:
        app.dependency_overrides[get_acting_user] = lambda: actor
        db.seed_user(
            user_id=actor.user_id,
            role=_ACTOR_DB_ROLE.get(actor.user_id, actor.role),
        )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _seed_in_review(db: FakeDB, claimant: str = REVIEWER_A, **extra):
    return db.seed_packet(
        packet_status="in_review",
        claimed_by_user_id=claimant,
        claimed_at="2026-07-13T00:00:00+00:00",
        **extra,
    )


# ══════════════════════════════════════════════════════════════════════════
# approve
# ══════════════════════════════════════════════════════════════════════════

def test_approve_claimant_success():
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/approve", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "approved"

    # claim fields cleared after success
    assert body["claimed_by_user_id"] is None
    assert body["claimed_at"] is None

    # correct audit event written
    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "approve"
    assert ev["actor_type"] == "user"
    assert ev["actor_id"] == REVIEWER_A
    assert ev["reason"] is None
    assert ev["metadata"] == {"actor_role": "reviewer", "authority_basis": "governance_reviewer"}


def test_approve_wrong_claimant_denied_without_admin_role():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_B, role="reviewer", display_name="B")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/approve", json={})
    assert res.status_code == 403
    # nothing changed
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.events == []


def test_approve_admin_override_requires_reason():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/approve", json={})
    assert res.status_code == 422
    assert db.packets[0]["packet_status"] == "in_review"


def test_approve_admin_override_success_with_reason():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post(
        "/admin/intake/pkt-1/approve",
        json={"override_reason": "reviewer unavailable, policy exception"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "approved"
    assert body["claimed_by_user_id"] is None

    ev = db.events[0]
    assert ev["event_type"] == "approve"
    assert ev["actor_id"] == ADMIN_1
    assert ev["reason"] == "reviewer unavailable, policy exception"
    assert ev["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "founder_ceo_override",
        "override": True,
        "claimant_user_id": REVIEWER_A,
    }


def test_approve_non_in_review_packet_rejected():
    db = FakeDB()
    db.seed_packet(packet_status="pending_review", claimed_by_user_id=None, claimed_at=None)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/approve", json={})
    assert res.status_code == 409
    assert db.events == []


def test_approve_failed_event_insert_rolls_back_transition():
    """
    Task #44 correction: approve_packet() now calls the single-transaction
    operations.approve_intake_packet RPC (migration 017). This test proves
    the fix for the defect Brad flagged in the prior implementation — if the
    event insert fails, the packet transition must be rolled back with it,
    not merely reported as an error while the transition silently commits.
    db.simulate_event_insert_failure makes the fake RPC raise right where
    the real function's INSERT would fail; FakeRpcCall.execute() restores
    its pre-call snapshot of every table on any exception, so this asserts
    genuine rollback, not just the HTTP status code.
    """
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    _make_client(db, actor)  # sets dependency_overrides + seeds actor's DB role
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/approve", json={})

    assert res.status_code == 500
    # The fix made visible: the transition did NOT commit...
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    # ...and no event was recorded either — both sides of the rollback hold.
    assert db.events == []


def test_return_failed_event_insert_rolls_back_transition():
    """Return-side equivalent of the approve rollback proof above."""
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    _make_client(db, actor)  # sets dependency_overrides + seeds actor's DB role
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/return", json={"reason": "missing evidence photo"})

    assert res.status_code == 500
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.packets[0]["return_reason"] is None
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# return
# ══════════════════════════════════════════════════════════════════════════

def test_return_claimant_success():
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/return", json={"reason": "missing evidence photo"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "returned"
    assert body["return_reason"] == "missing evidence photo"

    # claim fields cleared after success
    assert body["claimed_by_user_id"] is None
    assert body["claimed_at"] is None

    # correct audit event written, full reason preserved
    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "return"
    assert ev["actor_type"] == "user"
    assert ev["actor_id"] == REVIEWER_A
    assert ev["reason"] == "missing evidence photo"
    assert ev["metadata"] == {"actor_role": "reviewer", "authority_basis": "governance_reviewer"}


def test_return_wrong_claimant_non_admin_denied():
    """
    Founder/CEO governance clarification (2026-07-16): return is no longer
    strictly claimant-only, but a non-admin, non-claimant reviewer is still
    denied — only the claimant or an Administrator may return.
    """
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_B, role="reviewer", display_name="B")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/return", json={"reason": "valid reason"})
    assert res.status_code == 403
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.events == []


def test_return_admin_override_success():
    """
    Founder/CEO governance clarification (2026-07-16): return's prior
    claimant-only-no-override rule was the "artificial restriction" Brad
    flagged. An Administrator (which is how the Founder/CEO acts today, per
    the migration 017 header note) may now override-return using the
    existing mandatory reason field, and the event metadata records both the
    acting admin's role and the override/claimant details.
    """
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post(
        "/admin/intake/pkt-1/return",
        json={"reason": "claimant unavailable, CEO reviewing directly"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "returned"
    assert body["return_reason"] == "claimant unavailable, CEO reviewing directly"
    assert body["claimed_by_user_id"] is None
    assert body["claimed_at"] is None

    ev = db.events[0]
    assert ev["event_type"] == "return"
    assert ev["actor_id"] == ADMIN_1
    assert ev["reason"] == "claimant unavailable, CEO reviewing directly"
    assert ev["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "founder_ceo_override",
        "override": True,
        "claimant_user_id": REVIEWER_A,
    }


def test_return_blank_reason_rejected():
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/return", json={"reason": "   "})
    assert res.status_code == 422
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.events == []


def test_return_non_in_review_packet_rejected():
    db = FakeDB()
    db.seed_packet(packet_status="approved", claimed_by_user_id=None, claimed_at=None)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/return", json={"reason": "valid reason"})
    assert res.status_code == 409
    assert db.events == []


def test_return_does_not_touch_packet_data():
    """DEC000001 §5.2: no intake.review.* command may mutate packet_data."""
    db = FakeDB()
    _seed_in_review(db)
    db.packets[0]["packet_data"] = {"dishes": ["untouched"]}
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/return", json={"reason": "needs a fix"})
    assert res.status_code == 200, res.text
    assert db.packets[0]["packet_data"] == {"dishes": ["untouched"]}
