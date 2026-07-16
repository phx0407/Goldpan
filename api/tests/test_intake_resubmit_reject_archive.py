"""
api/tests/test_intake_resubmit_reject_archive.py — DEC000001 validation for
intake.packet.resubmit (CMD000034, §5.1/§6), intake.packet.reject
(CMD000009, §5.10), and intake.packet.archive (CMD000011, §5.11), Task #45.

Same FastAPI TestClient + FakeSupabaseClient/dependency-override pattern as
api/tests/test_intake_claim_release.py and api/tests/test_intake_edit_payload.py.
Each command is backed by a single-transaction RPC in supabase/migrations/
019_intake_edit_resubmit_reject_archive_rpcs.sql, emulated by
api/tests/fake_supabase.py's _fake_resubmit_intake_packet /
_fake_reject_intake_packet / _fake_archive_intake_packet, including genuine
snapshot/restore rollback simulation on a simulated event-insert failure.

No live database, no migration 019 execution — pure in-process behavior.
"""

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from api.deps import ActingUser, get_acting_user, get_supabase, verify_admin_key
from api.tests.conftest import app
from api.tests.fake_supabase import FakeDB, FakeSupabaseClient

SPECIALIST_1  = "55555555-5555-5555-5555-555555555555"   # Intake Specialist
REVIEWER_A    = "11111111-1111-1111-1111-111111111111"   # claimant in most reject/archive tests
REVIEWER_B    = "22222222-2222-2222-2222-222222222222"   # a different Governance Reviewer
ADMIN_1       = "33333333-3333-3333-3333-333333333333"
INACTIVE_1    = "77777777-7777-7777-7777-777777777777"

_ACTOR_DB_ROLE = {
    SPECIALIST_1: "canvasser",
    REVIEWER_A:   "reviewer",
    REVIEWER_B:   "reviewer",
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
        "packet_data": {"restaurant": {"restaurant_name": "R"}},
        "return_reason": "missing evidence",
        "claimed_by_user_id": None,
        "claimed_at": None,
    }
    fields.update(extra)
    return db.seed_packet(**fields)


def _seed_in_review(db: FakeDB, claimant: str = REVIEWER_A, **extra):
    fields = {
        "packet_status": "in_review",
        "packet_data": {"restaurant": {"restaurant_name": "R"}},
        "claimed_by_user_id": claimant,
        "claimed_at": "2026-07-13T00:00:00+00:00",
    }
    fields.update(extra)
    return db.seed_packet(**fields)


def _seed_rejected(db: FakeDB, **extra):
    fields = {
        "packet_status": "rejected",
        "packet_data": {"restaurant": {"restaurant_name": "R"}},
        "claimed_by_user_id": None,
        "claimed_at": None,
    }
    fields.update(extra)
    return db.seed_packet(**fields)


def _seed_ingested(db: FakeDB, **extra):
    fields = {
        "packet_status": "ingested",
        "packet_data": {"restaurant": {"restaurant_name": "R"}},
        "claimed_by_user_id": None,
        "claimed_at": None,
        "ingested_at": "2026-07-14T00:00:00+00:00",
    }
    fields.update(extra)
    return db.seed_packet(**fields)


# ══════════════════════════════════════════════════════════════════════════
# resubmit
# ══════════════════════════════════════════════════════════════════════════

def test_resubmit_success_returns_to_pending_review():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/resubmit", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "pending_review"
    assert body["return_reason"] is None

    assert db.packets[0]["packet_data"] == {"restaurant": {"restaurant_name": "R"}}  # untouched

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "resubmit"
    assert ev["actor_id"] == SPECIALIST_1
    assert ev["metadata"] == {"actor_role": "canvasser", "authority_basis": "intake_specialist"}


def test_resubmit_with_reason_recorded():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/resubmit", json={"reason": "addressed feedback"})
    assert res.status_code == 200, res.text
    assert db.events[0]["reason"] == "addressed feedback"


def test_resubmit_non_returned_packet_rejected():
    db = FakeDB()
    db.seed_packet(packet_status="pending_review", packet_data={"a": 1})
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/resubmit", json={})
    assert res.status_code == 409
    assert db.events == []


def test_resubmit_governance_reviewer_denied():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/resubmit", json={})
    assert res.status_code == 403
    assert db.packets[0]["packet_status"] == "returned"
    assert db.events == []


def test_resubmit_admin_denied_no_override_exists():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/resubmit", json={})
    assert res.status_code == 403
    assert db.events == []


def test_resubmit_inactive_actor_denied():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=INACTIVE_1, role="canvasser", display_name="Inactive")
    client = _make_client(db, actor, actor_is_active=False)

    res = client.post("/admin/intake/pkt-1/resubmit", json={})
    assert res.status_code == 403
    assert db.events == []


def test_resubmit_failed_event_insert_rolls_back_transition():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    _make_client(db, actor)
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/resubmit", json={})

    assert res.status_code == 500
    assert db.packets[0]["packet_status"] == "returned"
    assert db.packets[0]["return_reason"] == "missing evidence"
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# reject
# ══════════════════════════════════════════════════════════════════════════

def test_reject_claimant_success():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "duplicate submission"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "rejected"
    assert body["claimed_by_user_id"] is None
    assert body["claimed_at"] is None

    assert db.packets[0]["packet_data"] == {"restaurant": {"restaurant_name": "R"}}  # untouched

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "reject"
    assert ev["actor_id"] == REVIEWER_A
    assert ev["reason"] == "duplicate submission"
    assert ev["metadata"] == {
        "actor_role": "reviewer",
        "authority_basis": "governance_reviewer",
        "override": False,
        "claimant_user_id": REVIEWER_A,
    }


def test_reject_claimant_who_is_admin_self_rejects_not_override():
    """
    A claimant who happens to hold the 'admin' role rejecting their OWN claim
    is still an ordinary (non-override) rejection: authority_basis is
    governance_reviewer and override is False, per Brad's 2026-07-16
    correction — override status turns on whether the actor differs from
    the claimant, not on the actor's raw DB role.
    """
    db = FakeDB()
    _seed_in_review(db, claimant=ADMIN_1)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "evidence irreparably conflicting"})
    assert res.status_code == 200, res.text
    assert db.events[0]["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "governance_reviewer",
        "override": False,
        "claimant_user_id": ADMIN_1,
    }


def test_reject_admin_override_success():
    """
    Founder/CEO override (2026-07-16 governance correction): the 'admin'
    adapter may reject a packet claimed by someone else. Requires a
    non-blank reason (reused as the override justification, same precedent
    as return_intake_packet) and is logged distinctly with
    actor_role=admin, authority_basis=founder_ceo_override, override=true,
    and the prior claimant's ID.
    """
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "Founder/CEO override: evidence unresolvable"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["packet_status"] == "rejected"
    assert body["claimed_by_user_id"] is None

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "reject"
    assert ev["actor_id"] == ADMIN_1
    assert ev["reason"] == "Founder/CEO override: evidence unresolvable"
    assert ev["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "founder_ceo_override",
        "override": True,
        "claimant_user_id": REVIEWER_A,
    }


def test_reject_admin_override_blank_reason_rejected():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "  "})
    assert res.status_code == 422
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.events == []


def test_reject_blank_reason_rejected():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "  "})
    assert res.status_code == 422
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.events == []


def test_reject_non_claimant_reviewer_denied():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_B, role="reviewer", display_name="Reviewer B")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "trying to reject someone else's claim"})
    assert res.status_code == 403
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.events == []


def test_reject_non_admin_non_claimant_denied_no_override():
    """
    Non-claimant reviewers (any role other than 'admin') still have no
    override path — this is the same case as
    test_reject_non_claimant_reviewer_denied, restated explicitly to make
    clear the override path is admin-only, not open to any non-claimant.
    """
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_B, role="reviewer", display_name="Reviewer B")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "override attempt"})
    assert res.status_code == 403
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.events == []


def test_reject_non_in_review_packet_rejected():
    db = FakeDB()
    _seed_returned(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "not applicable"})
    assert res.status_code == 409
    assert db.events == []


def test_reject_failed_event_insert_rolls_back_transition():
    db = FakeDB()
    _seed_in_review(db, claimant=REVIEWER_A)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    _make_client(db, actor)
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/reject", json={"reason": "duplicate submission"})

    assert res.status_code == 500
    assert db.packets[0]["packet_status"] == "in_review"
    assert db.packets[0]["claimed_by_user_id"] == REVIEWER_A
    assert db.events == []


# ══════════════════════════════════════════════════════════════════════════
# archive
# ══════════════════════════════════════════════════════════════════════════

def test_archive_rejected_packet_by_reviewer_success():
    db = FakeDB()
    _seed_rejected(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "retention period elapsed"})
    assert res.status_code == 200, res.text

    assert db.packets[0]["packet_status"] == "rejected"  # unchanged
    assert db.packets[0]["archived_at"] is not None
    assert db.packets[0]["archived_by_user_id"] == REVIEWER_A

    assert len(db.events) == 1
    ev = db.events[0]
    assert ev["event_type"] == "archive"
    assert ev["actor_id"] == REVIEWER_A
    assert ev["reason"] == "retention period elapsed"
    assert ev["metadata"] == {
        "actor_role": "reviewer",
        "authority_basis": "governance_reviewer",
        "source_status": "rejected",
    }


def test_archive_ingested_packet_by_admin_success():
    """Founder/CEO override adapter may archive an eligible ingested packet — a non-admin reviewer may not (see below)."""
    db = FakeDB()
    _seed_ingested(db)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "cleanup"})
    assert res.status_code == 200, res.text
    assert db.packets[0]["packet_status"] == "ingested"  # unchanged
    assert db.packets[0]["archived_at"] is not None
    assert db.packets[0]["archived_by_user_id"] == ADMIN_1
    assert db.events[0]["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "founder_ceo_override",
        "source_status": "ingested",
    }


def test_archive_rejected_packet_by_admin_success():
    """Founder/CEO override adapter may also archive an eligible rejected packet."""
    db = FakeDB()
    _seed_rejected(db)
    actor = ActingUser(user_id=ADMIN_1, role="admin", display_name="Admin")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "admin cleanup"})
    assert res.status_code == 200, res.text
    assert db.events[0]["metadata"] == {
        "actor_role": "admin",
        "authority_basis": "founder_ceo_override",
        "source_status": "rejected",
    }


def test_archive_ingested_packet_by_non_admin_reviewer_denied():
    """A non-admin Governance Reviewer may not archive an ingested packet — only a rejected one."""
    db = FakeDB()
    _seed_ingested(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "cleanup"})
    assert res.status_code == 403
    assert db.packets[0]["archived_at"] is None
    assert db.events == []


def test_archive_intake_specialist_denied():
    """Intake Specialists may never archive, regardless of packet status."""
    db = FakeDB()
    _seed_rejected(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "cleanup"})
    assert res.status_code == 403
    assert db.packets[0]["archived_at"] is None
    assert db.events == []


def test_archive_intake_specialist_denied_ingested():
    db = FakeDB()
    _seed_ingested(db)
    actor = ActingUser(user_id=SPECIALIST_1, role="canvasser", display_name="Specialist")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "cleanup"})
    assert res.status_code == 403
    assert db.packets[0]["archived_at"] is None
    assert db.events == []


def test_archive_non_eligible_status_rejected():
    db = FakeDB()
    _seed_in_review(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "premature"})
    assert res.status_code == 409
    assert db.packets[0]["archived_at"] is None
    assert db.events == []


def test_archive_duplicate_archival_rejected():
    db = FakeDB()
    _seed_rejected(db, archived_at="2026-07-15T00:00:00+00:00", archived_by_user_id=REVIEWER_B)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "second attempt"})
    assert res.status_code == 409
    # Original archival attribution untouched.
    assert db.packets[0]["archived_by_user_id"] == REVIEWER_B
    assert db.events == []


def test_archive_blank_reason_rejected():
    db = FakeDB()
    _seed_rejected(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    client = _make_client(db, actor)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": ""})
    assert res.status_code == 422
    assert db.packets[0]["archived_at"] is None
    assert db.events == []


def test_archive_inactive_actor_denied():
    db = FakeDB()
    _seed_rejected(db)
    actor = ActingUser(user_id=INACTIVE_1, role="canvasser", display_name="Inactive")
    client = _make_client(db, actor, actor_is_active=False)

    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "cleanup"})
    assert res.status_code == 403
    assert db.packets[0]["archived_at"] is None
    assert db.events == []


def test_archive_failed_event_insert_rolls_back_archival():
    db = FakeDB()
    _seed_rejected(db)
    actor = ActingUser(user_id=REVIEWER_A, role="reviewer", display_name="Reviewer A")
    _make_client(db, actor)
    db.simulate_event_insert_failure = True

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/admin/intake/pkt-1/archive", json={"reason": "retention period elapsed"})

    assert res.status_code == 500
    assert db.packets[0]["archived_at"] is None
    assert db.packets[0]["archived_by_user_id"] is None
    assert db.events == []
