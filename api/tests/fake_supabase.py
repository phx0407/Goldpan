"""
api/tests/fake_supabase.py — minimal PostgREST-chain test double.

Not a real Supabase/PostgREST client. It emulates only the specific method
chains that api/routers/intake.py's claim/release/approve/return endpoints
actually call (`.schema().table().select()/.update()/.insert().eq()/.is_()
.limit().execute()`), against small in-memory tables, so the endpoint
functions can be exercised through FastAPI's TestClient without a live
Supabase/Postgres instance.

Deliberately reproduces the one behavior these tests care about most: a
conditional `.update(...).eq(...).eq(...).execute()` only applies (and only
returns a row) when every `.eq()`/`.is_()` filter matches the row currently
in the table — i.e. it is a stand-in for PostgREST's real conditional-UPDATE
semantics, which is exactly the mechanism DEC000001 §5.4/§5.5 requires and
that these tests are validating.

Also emulates `.rpc(name, params).execute()` for the four single-transaction
RPCs introduced in supabase/migrations/017_intake_review_decision_rpcs.sql
(operations.approve_intake_packet / operations.return_intake_packet) and
supabase/migrations/018_intake_claim_release_rpcs.sql
(operations.claim_intake_packet / operations.release_intake_packet — task #43
correction). Each fake RPC implementation mirrors the real plpgsql function's
logic against FakeDB's in-memory tables, snapshotting the affected tables
first and restoring the snapshot if anything raises — a genuine rollback
simulation, not just "the response was an error." This is what lets a test
assert the packet row was never left mid-transitioned after a simulated
event-insert failure, per task #44's transactional-integrity correction
(and its task #43 claim/release extension), rather than merely asserting
the HTTP status code.
"""

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

from postgrest.exceptions import APIError


class FakeResult:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data


class FakeQuery:
    def __init__(self, db: "FakeDB", table_name: str):
        self._db = db
        self._table_name = table_name
        self._eq_filters: List[tuple] = []
        self._is_filters: List[tuple] = []
        self._select_cols: Optional[str] = None
        self._update_fields: Optional[Dict[str, Any]] = None
        self._insert_row: Optional[Dict[str, Any]] = None

    # ── chain methods ───────────────────────────────────────────────────────
    def select(self, cols: str) -> "FakeQuery":
        self._select_cols = cols
        return self

    def eq(self, col: str, val: Any) -> "FakeQuery":
        self._eq_filters.append((col, val))
        return self

    def is_(self, col: str, val: Any) -> "FakeQuery":
        self._is_filters.append((col, val))
        return self

    def limit(self, n: int) -> "FakeQuery":
        return self

    def order(self, *a, **kw) -> "FakeQuery":
        return self

    def update(self, fields: Dict[str, Any]) -> "FakeQuery":
        self._update_fields = fields
        return self

    def insert(self, row: Dict[str, Any]) -> "FakeQuery":
        self._insert_row = row
        return self

    # ── terminal ─────────────────────────────────────────────────────────
    def execute(self) -> FakeResult:
        table = self._db.tables[self._table_name]

        if self._insert_row is not None:
            row = deepcopy(self._insert_row)
            row.setdefault("event_id", f"evt-{len(self._db.events_log) + 1}")
            self._db.events_log.append(row)
            table.append(row)
            return FakeResult([deepcopy(row)])

        matches = [r for r in table if self._row_matches(r)]

        if self._update_fields is not None:
            if not matches:
                return FakeResult([])
            # Real PostgREST would apply to every matching row; packet_id is
            # always one of our filters in practice, so this is always 0 or 1.
            for r in matches:
                r.update(self._update_fields)
            return FakeResult([deepcopy(r) for r in matches])

        return FakeResult([deepcopy(r) for r in matches])

    def _row_matches(self, row: Dict[str, Any]) -> bool:
        for col, val in self._eq_filters:
            if row.get(col) != val:
                return False
        for col, val in self._is_filters:
            # Only "null" is used by the endpoints under test.
            if val == "null" and row.get(col) is not None:
                return False
        return True


class FakeDB:
    """Holds the in-memory tables. One instance per test."""

    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            "intake_packets": [],
            "intake_packet_events": [],
            "users": [],
        }
        self.events_log: List[Dict[str, Any]] = []

        # Test hook only — has no real-RPC equivalent. Set to True to make
        # the next fake RPC call raise after mutating its in-memory rows but
        # before "committing" (i.e. before the snapshot taken in
        # FakeRpcCall.execute() is released), so the test can assert the
        # snapshot restore actually reverted the packet row — proving
        # rollback, not just an error response. See
        # test_approve_failed_event_insert_does_not_report_success and its
        # return-side equivalent.
        self.simulate_event_insert_failure: bool = False

    def seed_user(self, user_id: str, role: str, is_active: bool = True) -> Dict[str, Any]:
        """
        Seed operations.users for the fake decision RPCs' admin-override role
        lookup (mirrors operations.approve_intake_packet's `SELECT role FROM
        operations.users WHERE user_id = ... AND is_active = true`, migration
        017). _make_client() in test_intake_review_decisions.py auto-seeds
        the acting user, so most tests never need to call this directly.
        """
        row = {"user_id": user_id, "role": role, "is_active": is_active}
        self.tables["users"] = [r for r in self.tables["users"] if r["user_id"] != user_id]
        self.tables["users"].append(row)
        return row

    def seed_packet(self, **fields: Any) -> Dict[str, Any]:
        row = {
            "packet_id":              "pkt-1",
            "restaurant_external_id": "R-1",
            "restaurant_name":        "Test Restaurant",
            "restaurant_id":          None,
            "packet_status":          "pending_review",
            "canvass_date":           "2026-07-01",
            "dish_count":             0,
            "review_flag_count":      0,
            "evidence_score_overall": None,
            "agent_version":          None,
            "model_used":             None,
            "reviewer_notes":         None,
            "return_reason":          None,
            "submitted_at":           "2026-07-01T00:00:00+00:00",
            "reviewed_at":            None,
            "reviewed_by":            None,
            "ingested_at":            None,
            "claimed_by_user_id":     None,
            "claimed_at":             None,
        }
        row.update(fields)
        self.tables["intake_packets"].append(row)
        return row

    @property
    def events(self) -> List[Dict[str, Any]]:
        return self.tables["intake_packet_events"]

    @property
    def packets(self) -> List[Dict[str, Any]]:
        return self.tables["intake_packets"]


def _find_packet(db: FakeDB, packet_id: str) -> Optional[Dict[str, Any]]:
    for row in db.tables["intake_packets"]:
        if row["packet_id"] == packet_id:
            return row  # live reference — mutated in place by the impls below
    return None


def _lookup_user_role(db: FakeDB, user_id: str) -> Optional[str]:
    for row in db.tables["users"]:
        if row["user_id"] == user_id and row.get("is_active"):
            return row["role"]
    return None


def _insert_fake_event(db: FakeDB, **fields: Any) -> None:
    row = dict(fields)
    row.setdefault("event_id", f"evt-{len(db.events_log) + 1}")
    db.events_log.append(row)
    db.tables["intake_packet_events"].append(row)


def _fake_approve_intake_packet(db: FakeDB, params: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors operations.approve_intake_packet (migration 017), step for step."""
    packet_id       = params["p_packet_id"]
    actor_user_id   = params["p_actor_user_id"]
    override_reason = params.get("p_override_reason")
    reviewer_notes  = params.get("p_reviewer_notes")

    if actor_user_id is None:
        raise APIError({"message": "p_actor_user_id is required", "code": "GP422"})

    packet = _find_packet(db, packet_id)
    if packet is None:
        raise APIError({"message": f"Packet '{packet_id}' not found.", "code": "GP404"})

    claimant_id = packet.get("claimed_by_user_id")
    if packet["packet_status"] != "in_review" or not claimant_id:
        raise APIError({
            "message": "Packet must be in_review and claimed before it can be approved.",
            "code": "GP409",
        })

    is_override = actor_user_id != claimant_id

    # Role is always resolved now (not only for the override branch) so
    # every event carries the acting user's role/authority in its metadata
    # — Founder/CEO governance clarification, mirrors migration 017.
    actor_role = _lookup_user_role(db, actor_user_id)

    # Organizational authority basis for the audit trail, distinct from
    # actor_role's raw DB-role value — governance-alignment correction,
    # mirrors migration 017. Only 'reviewer' or 'admin' ever reach this
    # point (every other role was already rejected above).
    authority_basis = "founder_ceo_override" if actor_role == "admin" else "governance_reviewer"

    if is_override:
        if actor_role != "admin":
            raise APIError({
                "message": "Only the current claimant or an Administrator may approve this packet.",
                "code": "GP403",
            })
        if not override_reason or not override_reason.strip():
            raise APIError({
                "message": "An Administrator override approval requires a non-blank reason.",
                "code": "GP422",
            })

    packet["packet_status"]      = "approved"
    packet["reviewed_at"]        = "2026-07-13T00:00:00+00:00"
    packet["reviewed_by"]        = actor_user_id
    packet["return_reason"]      = None
    packet["claimed_by_user_id"] = None
    packet["claimed_at"]         = None
    if reviewer_notes is not None:
        packet["reviewer_notes"] = reviewer_notes

    if db.simulate_event_insert_failure:
        # Simulates the event INSERT failing inside the transaction (append-
        # only trigger firing unexpectedly, actor-validation trigger, a
        # dropped connection — the real cause doesn't matter). The packet
        # mutation above already happened on the live row; FakeRpcCall.
        # execute() must undo it via the pre-call snapshot.
        raise RuntimeError("simulated event-log insert failure")

    metadata = {"actor_role": actor_role, "authority_basis": authority_basis}
    if is_override:
        metadata.update({"override": True, "claimant_user_id": claimant_id})

    _insert_fake_event(
        db,
        packet_id=packet_id, event_type="approve",
        actor_type="user", actor_id=actor_user_id,
        reason=override_reason if is_override else None,
        metadata=metadata,
    )
    return deepcopy(packet)


def _fake_return_intake_packet(db: FakeDB, params: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors operations.return_intake_packet (migration 017), step for step."""
    packet_id      = params["p_packet_id"]
    actor_user_id  = params["p_actor_user_id"]
    reason         = params.get("p_reason")
    reviewer_notes = params.get("p_reviewer_notes")

    if actor_user_id is None:
        raise APIError({"message": "p_actor_user_id is required", "code": "GP422"})

    if not reason or not reason.strip():
        raise APIError({"message": "A non-blank reason is required to return a packet.", "code": "GP422"})

    packet = _find_packet(db, packet_id)
    if packet is None:
        raise APIError({"message": f"Packet '{packet_id}' not found.", "code": "GP404"})

    claimant_id = packet.get("claimed_by_user_id")
    if packet["packet_status"] != "in_review" or not claimant_id:
        raise APIError({
            "message": "Packet must be in_review and claimed before it can be returned.",
            "code": "GP409",
        })

    is_override = actor_user_id != claimant_id

    # Role is always resolved now (not only for the override branch) so
    # every event carries the acting user's role/authority in its metadata
    # — Founder/CEO governance clarification, mirrors migration 017. The
    # admin-override path itself is new here too: return was previously
    # claimant-only with no override at all (the "artificial restriction"
    # Brad flagged), superseded by this clarification.
    actor_role = _lookup_user_role(db, actor_user_id)

    # Organizational authority basis for the audit trail, distinct from
    # actor_role's raw DB-role value — governance-alignment correction,
    # mirrors migration 017. Only 'reviewer' or 'admin' ever reach this
    # point (every other role was already rejected above).
    authority_basis = "founder_ceo_override" if actor_role == "admin" else "governance_reviewer"

    if is_override and actor_role != "admin":
        raise APIError({
            "message": "Only the current claimant or an Administrator may return this packet.",
            "code": "GP403",
        })

    packet["packet_status"]      = "returned"
    packet["return_reason"]      = reason
    packet["reviewed_at"]        = "2026-07-13T00:00:00+00:00"
    packet["reviewed_by"]        = actor_user_id
    packet["claimed_by_user_id"] = None
    packet["claimed_at"]         = None
    if reviewer_notes is not None:
        packet["reviewer_notes"] = reviewer_notes

    if db.simulate_event_insert_failure:
        raise RuntimeError("simulated event-log insert failure")

    metadata = {"actor_role": actor_role, "authority_basis": authority_basis}
    if is_override:
        metadata.update({"override": True, "claimant_user_id": claimant_id})

    _insert_fake_event(
        db,
        packet_id=packet_id, event_type="return",
        actor_type="user", actor_id=actor_user_id,
        reason=reason,
        metadata=metadata,
    )
    return deepcopy(packet)


def _fake_claim_intake_packet(db: FakeDB, params: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors operations.claim_intake_packet (migration 018), step for step."""
    packet_id     = params["p_packet_id"]
    actor_user_id = params["p_actor_user_id"]

    if actor_user_id is None:
        raise APIError({"message": "p_actor_user_id is required", "code": "GP422"})

    # 1. Authorization gate, independent of packet state — reviewer OR admin
    # (task #43 correction's deliberate widening from reviewer-only).
    actor_role = _lookup_user_role(db, actor_user_id)
    if actor_role != "reviewer" and actor_role != "admin":
        raise APIError({
            "message": "Only Governance Reviewers or Administrators may claim a packet for review.",
            "code": "GP403",
        })

    # Organizational authority basis for the audit trail, distinct from
    # actor_role's raw DB-role value — governance-alignment correction,
    # mirrors migration 018. Only 'reviewer' or 'admin' ever reach this
    # point (every other role was already rejected above).
    authority_basis = "founder_ceo_override" if actor_role == "admin" else "governance_reviewer"

    packet = _find_packet(db, packet_id)
    if packet is None:
        raise APIError({"message": f"Packet '{packet_id}' not found.", "code": "GP404"})

    if packet["packet_status"] != "pending_review" or packet.get("claimed_by_user_id") is not None:
        raise APIError({
            "message": "Packet is not available to claim (already claimed, or not pending_review).",
            "code": "GP409",
        })

    packet["packet_status"]      = "in_review"
    packet["claimed_by_user_id"] = actor_user_id
    packet["claimed_at"]         = "2026-07-13T00:00:00+00:00"

    if db.simulate_event_insert_failure:
        raise RuntimeError("simulated event-log insert failure")

    _insert_fake_event(
        db,
        packet_id=packet_id, event_type="claim",
        actor_type="user", actor_id=actor_user_id,
        reason=None,
        metadata={"actor_role": actor_role, "authority_basis": authority_basis},
    )
    return deepcopy(packet)


def _fake_release_intake_packet(db: FakeDB, params: Dict[str, Any]) -> Dict[str, Any]:
    """Mirrors operations.release_intake_packet (migration 018), step for step."""
    packet_id     = params["p_packet_id"]
    actor_user_id = params["p_actor_user_id"]
    reason        = params.get("p_reason")

    if actor_user_id is None:
        raise APIError({"message": "p_actor_user_id is required", "code": "GP422"})

    packet = _find_packet(db, packet_id)
    if packet is None:
        raise APIError({"message": f"Packet '{packet_id}' not found.", "code": "GP404"})

    claimant_id = packet.get("claimed_by_user_id")
    if packet["packet_status"] != "in_review" or not claimant_id:
        raise APIError({
            "message": "Packet is not currently claimed / in_review.",
            "code": "GP409",
        })

    is_override = actor_user_id != claimant_id

    # Role is always resolved now (not only for the override branch) so
    # every event carries the acting user's role/authority in its metadata
    # — Founder/CEO governance clarification, mirrors migration 018.
    actor_role = _lookup_user_role(db, actor_user_id)

    # Organizational authority basis for the audit trail, distinct from
    # actor_role's raw DB-role value — governance-alignment correction,
    # mirrors migration 018. Only 'reviewer' or 'admin' ever reach this
    # point (every other role was already rejected above).
    authority_basis = "founder_ceo_override" if actor_role == "admin" else "governance_reviewer"

    if is_override:
        if actor_role != "admin":
            raise APIError({
                "message": "Only the current claimant or an Administrator may release this packet.",
                "code": "GP403",
            })
        if not reason or not reason.strip():
            raise APIError({
                "message": "An Administrator override release requires a non-blank reason.",
                "code": "GP422",
            })

    packet["packet_status"]      = "pending_review"
    packet["claimed_by_user_id"] = None
    packet["claimed_at"]         = None

    if db.simulate_event_insert_failure:
        raise RuntimeError("simulated event-log insert failure")

    _insert_fake_event(
        db,
        packet_id=packet_id, event_type="release",
        actor_type="user", actor_id=actor_user_id,
        reason=(reason if is_override else None),
        metadata={
            "actor_role": actor_role,
            "authority_basis": authority_basis,
            "override": is_override,
            "claimant_user_id": claimant_id,
        },
    )
    return deepcopy(packet)


_RPC_IMPLS: Dict[str, Callable[[FakeDB, Dict[str, Any]], Dict[str, Any]]] = {
    "approve_intake_packet": _fake_approve_intake_packet,
    "return_intake_packet":  _fake_return_intake_packet,
    "claim_intake_packet":   _fake_claim_intake_packet,
    "release_intake_packet": _fake_release_intake_packet,
}


class FakeRpcCall:
    """
    Stands in for the object supabase-py's `.rpc(name, params)` returns
    before `.execute()`. Emulates a single-transaction Postgres RPC: the
    affected tables are snapshotted before the fake implementation runs, and
    restored verbatim if the implementation raises anything — so a test can
    assert the packets table was NOT left mutated after a simulated failure,
    the same guarantee migration 017's real plpgsql functions get for free
    from being one statement in one transaction.
    """

    def __init__(self, db: FakeDB, name: str, params: Dict[str, Any]):
        self._db = db
        self._name = name
        self._params = params

    def execute(self) -> FakeResult:
        impl = _RPC_IMPLS.get(self._name)
        if impl is None:
            raise ValueError(f"FakeSupabaseClient.rpc(): no fake implementation for '{self._name}'")

        snapshot = {name: deepcopy(rows) for name, rows in self._db.tables.items()}
        events_log_snapshot = deepcopy(self._db.events_log)
        try:
            row = impl(self._db, self._params)
        except Exception:
            self._db.tables = snapshot
            self._db.events_log = events_log_snapshot
            raise
        return FakeResult(row)


class FakeSupabaseClient:
    """Stands in for supabase.Client — only .schema().table(...) and .rpc(...) are used."""

    def __init__(self, db: FakeDB):
        self._db = db

    def schema(self, name: str) -> "FakeSupabaseClient":
        return self

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self._db, name)

    def rpc(self, name: str, params: Dict[str, Any]) -> FakeRpcCall:
        return FakeRpcCall(self._db, name, params)
