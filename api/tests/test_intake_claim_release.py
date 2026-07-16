"""
api/tests/test_intake_claim_release.py — DEC000001 §5.3/§5.4/§5.5 validation
for intake.review.claim (CMD000003) and intake.review.release (CMD000004),
task #43 (corrected for transactional integrity).

No pre-existing test file covered claim/release before this correction —
task #43's original implementation shipped without dedicated test coverage.
This file is new, written alongside migration 018
(supabase/migrations/018_intake_claim_release_rpcs.sql) and the RPC-based
rewrite of claim_packet()/release_packet() in api/routers/intake.py, to the
same breadth and pattern as api/tests/test_intake_review_decisions.py
(task #44): concurrency/state-conflict cases, self-action vs. admin-override
cases, wrong-user denial, and a genuine rollback proof for a failed event
insert.

Uses FastAPI's TestClient against the real app/router wiring, with
dependency overrides swapping in a FakeSupabaseClient (api/tests/fake_supabase.py)
in place of a live Supabase connection, and a directly-injected ActingUser in
place of a real X-User-Id lookup. X-Admin-Key enforcement is overridden the
same way as in test_intake_review_decisions.py and is out of scope here.

claim_packet()/release_packet() now call a single Postgres RPC each
(operations.claim_intake_packet / operations.release_intake_packet,
supabase/migrations/018_intake_claim_release_rpcs.sql) instead of a
role-check + conditional UPDATE. FakeSupabaseClient.rpc(...)
(api/tests/fake_supabase.py) emulates those functions' logic, including
genuine snapshot/restore rollback if the fake implementation raises — this
is what lets the *_failed_event_insert_rolls_back_transition tests below
prove the packet row was never left mid-transitioned, not merely that the
HTTP response was an error.

No live database, no migration 018 execution — pure in-process behavior.
"""

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from api.deps import ActingUser, get_acting_user, get_supabase, verify_admin_key
from api.tests.conftest import app
from api.tests.fake_supabase import FakeDB, FakeSupabaseClient

REVIEWER_A    = "11111111-1111-1111-1111-111111111111"   # claimant in most tests
REVIEWER_B    = "22222222-2222-2222-2222-222222222222"   # a different Governance Reviewer
ADMIN_1       = "33333333-3333-3333-3333-333333333333"
SPECIALIST_1  = "44444444-4444-4444-4444-444444444444"   # neither reviewer nor admin

# DB role backing each constant above, used to auto-seed FakeDB's "users"
# table so the fake claim/release RPCs' role lookups (mirroring
# operations.claim_intake_packet / operations.release_intake_packet's own
# `SELECT role FROM operations.users`) resolve the way each test expects.
_ACTOR_DB_ROLE = {
    REVIEWER_A:   "reviewer",
    REVIEWER_B:   "reviewer",
    ADMIN_1:      "admin",
    SPECIALIST_1: "specialist",
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


def _seed_pending(db: FakeDB, **extra):
    return db.seed_packet(
        packet_status="pending_review",
        claimed_by_user_id=None,
        claimed_at=None,
        **extra,
    )


def _seed_in_review(db: FakeDB, claimant: str = REVIEWER_A, **extra):
    return db.seed_packet(
        packet_status="in_review",
        claimed_by_user_id=claimant,
        claimed_at="2026-07-13T00:00:00+00:00",
        **extra,
    )


# ══════════════════════════════════════════════════════════════════════════
# claim
# ══════════════════════════════════════════════════════════════════════════

def test_claim_reviewer_success():
    db = FakeDB()
    _seed_pending(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/claim", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "in_review"
    assert body["claimed_by_user_id"] == REVIEWER_A
    assert body["claimed_at"] is not None

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "claim"
    assert ev["actor_type"] == "user"
    assert ev["actor_id"] == REVIEWER_A
    assert ev["reason"] is None
    assert ev["metadata"] == {"actor_role": "reviewer", "authority_basis": "governance_reviewer"}


def test_claim_admin_success():
    """Task #43 correction's deliberate widening: admin authority may also claim."""
    db = FakeDB()
    _seed_pending(db)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/claim", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "in_review"
    assert body["claimed_by_user_id"] == ADMIN_1


def test_claim_wrong_role_denied():
    db = FakeDB()
    _seed_pending(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="specialist", display_name="S")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/claim", json={})
    assert res.status_code == 403
    assert db.packets[0]["packet_status"] == "pending_review"
    assert db.packets[0]["claimed_by_user_id"] is None
    assert db.events == []


def test_claim_already_claimed_conflict():
    """Concurrency case: a second reviewer cannot claim an already-claimed packet."""
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_B, role="reviewer", display_name="B")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/claim", json={})
    assert res.status_code == 409
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.events == []


def test_claim_non_pending_packet_conflict():
    db = FakeDB()
    db.seed_packet(packet_status="approved", claimed_by_user_id=None, claimed_at=None)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/claim", json={})
    assert res.status_code == 409
    assert db.events == []


def test_claim_nonexistent_packet_404():
    db = FakeDB()
    _seed_pending(db)  # seeds "pkt-1", not "pkt-404"
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-404/claim", json={})
    assert res.status_code == 404
    assert db.events == []


def test_claim_failed_event_insert_rolls_back_transition():
    """
    Task #43 correction: claim_packet() now calls the single-transaction
    operations.claim_intake_packet RPC (migration 018). This proves the same
    guarantee task #44 established for approve/return — if the event insert
    fails, the packet transition must be rolled back with it, not silently
    commit while the HTTP response reports an error.
    """
    db = FakeDB()
    _seed_pending(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    _make_client(db, actor)  # sets dependency_overrides + seeds actor's DB role
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/claim", json={})

    assert res.status_code == 500
    # The fix made visible: the transition did NOT commit...
    assert db.packets[0]["packet_status"] == "pending_review"
    assert db.packets[0]["claimed_by_user_id"] is None
    assert db.packets[0]["claimed_at"] is None
    # ...and no event was recorded either — both sides of the rollback hold.
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# release
# ══════════════════════════════════════════════════════════════════════════

def test_release_self_release_success():
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/release", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "pending_review"
    assert body["claimed_by_user_id"] is None
    assert body["claimed_at"] is None

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "release"
    assert ev["actor_type"] == "user"
    assert ev["actor_id"] == REVIEWER_A
    assert ev["reason"] is None
    assert ev["metadata"] == {
        "actor_role": "reviewer",
        "authority_basis": "governance_reviewer",
        "override": False,
        "claimant_user_id": REVIEWER_A,
    }


def test_release_wrong_user_non_admin_denied():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_B, role="reviewer", display_name="B")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/release", json={"reason": "trying to release someone else's claim"})
    assert res.status_code == 403
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.events == []


def test_release_admin_override_requires_reason():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/release", json={})
    assert res.status_code == 422
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.events == []


def test_release_admin_override_success_with_reason():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post(
        "/admin/intake/pkt-1/release",
        json={"reason": "claimant unavailable, freeing packet for another reviewer"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "pending_review"
    assert body["claimed_by_user_id"] is None
    assert body["claimed_at"] is None

    ev = db.events[0]
    assert ev["event_type"] == "release"
    assert ev["actor_id"] == ADMIN_1
    assert ev["reason"] == "claimant unavailable, freeing packet for another reviewer"
    assert ev["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "founder_ceo_override",
        "override": True,
        "claimant_user_id": REVIEWER_A,
    }


def test_release_non_in_review_packet_rejected():
    db = FakeDB()
    _seed_pending(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/release", json={})
    assert res.status_code == 409
    assert db.events == []


def test_release_failed_event_insert_rolls_back_transition():
    """Release-side equivalent of the claim rollback proof above."""
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="A")
    _make_client(db, actor)  # sets dependency_overrides + seeds actor's DB role
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/release", json={})

    assert res.status_code == 500
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.packets[0]["claimed_at"] is not None
    assert db.events == []
