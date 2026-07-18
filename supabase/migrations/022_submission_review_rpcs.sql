-- ============================================================
-- 022_submission_review_rpcs.sql
-- Restaurant Operations OS — RPC layer for DEC000002 (Restaurant
-- Update Submission state machine, v4.2), built against the schema
-- introduced in 021_submission_state_machine.sql.
--
-- SCOPE OF THIS MIGRATION — narrowed by explicit Founder instruction,
-- not by the original plan referenced in 021's own closing comment.
-- 021's footer anticipated this file would eventually hold claim /
-- release / return / approve / reject / convert_to_intake alongside
-- resubmit. This pass builds ONLY:
--
--   operations.resubmit_restaurant_update_submission
--     — DEC000002 §5.7-§5.8: state-transition mechanics for
--       submission.restaurant_update.resubmit (atomic parent/child
--       creation), per Founder ruling: "Build the resubmit RPC and
--       state-transition mechanics now, but do not expose an API
--       endpoint or assign invocation authority yet."
--
-- claim / release / return / approve / reject / convert_to_intake
-- remain future work, not attempted here. submission.
-- route_to_identity_review and submission.escalate_exception remain
-- blocked on downstream architecture that does not exist yet (021
-- judgment call 2, gap map §3) — per Founder ruling: "add only
-- DEC000002-authorized unconstrained submission placeholders. Do not
-- invent target tables, foreign keys, or fake routing behavior" —
-- already satisfied by 021's identity_review_item_id /
-- exception_request_id placeholder columns; no RPC for either is
-- added here or implied by this file's name.
--
-- Governance judgment calls made in this migration (flagged for
-- review, matching 021's own documentation convention):
--
--   1. Invocation authority is deliberately NOT assigned. §5.7:
--      "no actor category or role is defined for resubmit by this
--      decision" — unlike every RPC in 019
--      (edit_intake_packet_payload, resubmit_intake_packet,
--      reject_intake_packet, archive_intake_packet), this function
--      contains NO role check (no operations.users.role comparison
--      at all). It only requires p_actor_user_id to reference a real,
--      active operations.users row — that is a data-integrity
--      requirement (the events table's actor-validation trigger from
--      021 would reject a fabricated or inactive actor regardless),
--      not a stand-in for the authorization decision §5.7 and §7
--      item 5 defer. When that separate role/portal-origin decision
--      is eventually made, it may need to ADD a role check here — its
--      absence today is not evidence that "any active user" was ever
--      approved as the answer.
--
--   2. No GRANT EXECUTE is issued for this function — to anyone,
--      including service_role. An explicit REVOKE ALL ... FROM PUBLIC
--      follows the function definition. PostgreSQL grants EXECUTE on
--      newly created functions to PUBLIC by default (unlike tables,
--      which default to no access) — silently leaving this out would
--      NOT withhold invocation authority as instructed, it would
--      hand it to every authenticated database role by accident. No
--      other migration in this repo issues this REVOKE (checked:
--      no PUBLIC/REVOKE/ALTER DEFAULT PRIVILEGES usage anywhere in
--      migrations 001-021), so this is a new, deliberate pattern
--      introduced here, not a repo-wide default being followed.
--      Concretely: only the database owner / a superuser role (e.g.
--      `postgres`) can invoke this function right now. The API layer,
--      which normally calls through `service_role`, CANNOT call it
--      until a future migration adds the grant — which is exactly
--      "do not expose an API endpoint or assign invocation authority
--      yet."
--
--   3. §5.7: "emits a resubmit event (§5.10) on the parent and an
--      implicit creation record on the child." The event_type enum
--      (021) has no separate 'created' value — §5.10 itself confirms
--      this is intentional: `resubmit` was "renamed from
--      child_resubmission_created this revision to match the
--      formalized command name in §5.7 — same event, one name." Read
--      literally, this migration writes TWO event rows, both
--      event_type = 'resubmit': one keyed to the parent
--      (submission_id = parent, documenting "this row was resubmitted
--      into a new child") and one keyed to the child (submission_id =
--      child, documenting "this row was created by a resubmit" — the
--      "implicit creation record"). Each row's metadata
--      cross-references the other's submission_id so the pair is
--      reconstructable from either side without a join back through
--      resubmission_of_submission_id alone.
--
--   4. p_payload_json / p_description are NOT required to be jointly
--      non-null. §5.7 says only "the caller supplies the corrected
--      payload_json/description for the new child" — it does not
--      state a precondition-failure rule for supplying neither, and
--      011's original schema does not require either field to be
--      non-null on first creation either. Forcing "at least one" here
--      would be an invented guardrail this decision does not state.
--      Whatever is supplied replaces the parent's value via COALESCE;
--      whatever is omitted carries the parent's existing value
--      forward unchanged.
--
--   5. Every other column on the child row not addressed by
--      §5.7 (restaurant_id, partner_id, submitted_by_*, dish_id,
--      dish_name, attachment_*, verification_note, effective_date,
--      priority, source, ip_hash) is copied verbatim from the parent.
--      §5.7 frames resubmit as "the corrected payload" for what is
--      still, in the real world, the same submitter's same
--      underlying request — not an unrelated new submission — so the
--      child inherits the parent's descriptive/provenance data except
--      for the two fields (payload_json, description) the command
--      exists to correct. This mirrors how identity is validated:
--      021's trg_rusub_validate_resubmission_identity already
--      requires child.restaurant_id = parent.restaurant_id, which
--      only holds trivially true if restaurant_id is copied, not
--      re-supplied by the caller — so this function does not accept
--      restaurant_id (or any other carried-forward field) as a
--      parameter at all, removing any way to violate that trigger
--      from this RPC's own call surface.
-- ============================================================


-- ── operations.resubmit_restaurant_update_submission ──────────────────────
--
-- Implements submission.restaurant_update.resubmit per DEC000002 §5.7-§5.8:
--   1. Validate inputs.
--   2. Validate actor: must reference an active operations.users row.
--      NO role check — see judgment call 1 above.
--   3. Lock the parent row.
--   4. Verify the parent exists, is 'returned', and is not already
--      superseded (superseded_by_submission_id IS NULL) — §5.7
--      preconditions. Failure is an explicit error, never a silent
--      no-op (§5.7 "Failure mode").
--   5. Insert the child row: status = 'pending_review',
--      resubmission_of_submission_id = parent's id, payload_json /
--      description = COALESCE(supplied correction, parent's value),
--      every other content/provenance column copied from the parent
--      (judgment call 5). Disposition/claim/archival columns are left
--      at their table defaults (unassessed / null) — a fresh child
--      has no review history of its own yet.
--      021's trg_rusub_validate_resubmission_identity fires here
--      (BEFORE INSERT) and independently re-verifies the same-
--      restaurant-identity rule (§5.8) — not duplicated in this
--      function's own logic.
--   6. Update the parent: superseded_by_submission_id = child's id.
--      021's trg_rusub_prevent_chain_rewrite permits this because the
--      parent's superseded_by_submission_id was confirmed NULL in
--      step 4 — this is the ONE write the immutability trigger is
--      designed to allow, the original write, not a rewrite.
--      Together, steps 5-6 satisfy §5.7's atomicity requirement
--      (child insert + parent update, same transaction) and §5.8
--      rule 4 (linkage created atomically).
--   7. Insert two 'resubmit' events (judgment call 3 above): one on
--      the parent, one on the child, cross-referencing each other.
--   8. Return the new child row — the object the caller now has to
--      act on next.
--   9. Any RAISE aborts the whole function; nothing in steps 5-7
--      commits unless all of it does.
CREATE OR REPLACE FUNCTION operations.resubmit_restaurant_update_submission(
    p_submission_id  uuid,
    p_actor_user_id  uuid,
    p_payload_json   jsonb DEFAULT NULL,
    p_description    text  DEFAULT NULL
)
RETURNS operations.restaurant_update_submissions
LANGUAGE plpgsql
AS $$
DECLARE
    v_parent       operations.restaurant_update_submissions%ROWTYPE;
    v_child        operations.restaurant_update_submissions%ROWTYPE;
    v_actor_active boolean;
BEGIN
    -- 1.
    IF p_submission_id IS NULL THEN
        RAISE EXCEPTION 'p_submission_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    -- 2. No role check — DEC000002 §5.7 defines no actor category or
    -- role for resubmit. Only "is this a real, active user" is
    -- enforced here (see judgment call 1 in the file header).
    SELECT is_active INTO v_actor_active
    FROM operations.users
    WHERE user_id = p_actor_user_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Actor % does not reference an existing operations.users row', p_actor_user_id
            USING ERRCODE = 'GP404';
    ELSIF NOT v_actor_active THEN
        RAISE EXCEPTION 'Actor % references an inactive operations.users row', p_actor_user_id
            USING ERRCODE = 'GP403';
    END IF;

    -- 3.
    SELECT * INTO v_parent
    FROM operations.restaurant_update_submissions
    WHERE submission_id = p_submission_id
    FOR UPDATE;

    -- 4.
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission % not found', p_submission_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_parent.status <> 'returned' THEN
        RAISE EXCEPTION 'Submission % must be returned before it can be resubmitted (current status: %)', p_submission_id, v_parent.status
            USING ERRCODE = 'GP409';
    END IF;

    IF v_parent.superseded_by_submission_id IS NOT NULL THEN
        RAISE EXCEPTION 'Submission % has already been resubmitted (superseded by %)', p_submission_id, v_parent.superseded_by_submission_id
            USING ERRCODE = 'GP409';
    END IF;

    -- 5.
    INSERT INTO operations.restaurant_update_submissions (
        restaurant_id, partner_id,
        submitted_by_name, submitted_by_email, submitted_by_phone, submitted_by_role,
        submission_type, description, payload_json,
        dish_id, dish_name,
        attachment_url, attachment_filename, attachment_type,
        verification_note, effective_date,
        status, priority, source, ip_hash,
        resubmission_of_submission_id
    ) VALUES (
        v_parent.restaurant_id, v_parent.partner_id,
        v_parent.submitted_by_name, v_parent.submitted_by_email, v_parent.submitted_by_phone, v_parent.submitted_by_role,
        v_parent.submission_type,
        COALESCE(p_description, v_parent.description),
        COALESCE(p_payload_json, v_parent.payload_json),
        v_parent.dish_id, v_parent.dish_name,
        v_parent.attachment_url, v_parent.attachment_filename, v_parent.attachment_type,
        v_parent.verification_note, v_parent.effective_date,
        'pending_review', v_parent.priority, v_parent.source, v_parent.ip_hash,
        p_submission_id
    )
    RETURNING * INTO v_child;

    -- 6.
    UPDATE operations.restaurant_update_submissions
    SET superseded_by_submission_id = v_child.submission_id
    WHERE submission_id = p_submission_id;

    -- 7.
    INSERT INTO operations.restaurant_update_submission_events (
        submission_id, event_type, actor_type, actor_id,
        prior_status, resulting_status,
        prior_disposition_status, resulting_disposition_status,
        metadata
    ) VALUES (
        p_submission_id, 'resubmit', 'user', p_actor_user_id::text,
        v_parent.status, v_parent.status,
        v_parent.disposition_status, v_parent.disposition_status,
        jsonb_build_object(
            'resubmission_role', 'parent',
            'child_submission_id', v_child.submission_id
        )
    );

    INSERT INTO operations.restaurant_update_submission_events (
        submission_id, event_type, actor_type, actor_id,
        prior_status, resulting_status,
        prior_disposition_status, resulting_disposition_status,
        metadata
    ) VALUES (
        v_child.submission_id, 'resubmit', 'user', p_actor_user_id::text,
        NULL, v_child.status,
        NULL, v_child.disposition_status,
        jsonb_build_object(
            'resubmission_role', 'child',
            'parent_submission_id', p_submission_id
        )
    );

    -- 8.
    RETURN v_child;
END;
$$;

COMMENT ON FUNCTION operations.resubmit_restaurant_update_submission(uuid, uuid, jsonb, text) IS
    'DEC000002 §5.7-§5.8: single-transaction submission.restaurant_update.resubmit. '
    'Requires an active operations.users actor but enforces NO role — §5.7 defines no '
    'actor category for this command; invocation authority remains a separate, deferred '
    'decision (§7 item 5). Validates the parent is returned and not already superseded, '
    'creates a new pending_review child carrying the corrected payload_json/description '
    '(all other fields copied from the parent), sets parent.superseded_by_submission_id '
    'atomically with the child insert, and writes two cross-referenced resubmit events '
    '(one per row). EXECUTE is deliberately withheld from every role below (see the '
    'REVOKE immediately following this function) — built per Founder ruling to have the '
    'state-transition mechanics ready, without exposing an API endpoint or assigning '
    'invocation authority yet.';

-- Judgment call 2 (file header): PostgreSQL grants EXECUTE on new functions
-- to PUBLIC by default. Explicitly withdraw it, and issue NO GRANT EXECUTE
-- to service_role or authenticated — unlike every RPC in migration 019,
-- which all end with a GRANT. Only the database owner / a superuser role
-- can invoke this function until a future migration deliberately grants it.
REVOKE ALL ON FUNCTION operations.resubmit_restaurant_update_submission(uuid, uuid, jsonb, text)
    FROM PUBLIC;

-- ============================================================
-- End of 022_submission_review_rpcs.sql
--
-- Explicitly NOT done here:
--   - claim / release / return / approve / reject RPCs
--   - submission.convert_to_intake RPC
--   - submission.route_to_identity_review / submission.escalate_exception
--     — blocked, no downstream architecture exists (021 judgment call 2)
--   - Any GRANT EXECUTE on resubmit_restaurant_update_submission, any
--     FastAPI router / X-User-Id request handling, or UI
--
-- Do not run this migration until it has been reviewed. Not executed
-- against any database.
-- ============================================================
