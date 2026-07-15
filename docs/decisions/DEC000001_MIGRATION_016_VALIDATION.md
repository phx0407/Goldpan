# DEC000001 — Migration 016 Validation Note

**Migration:** `supabase/migrations/016_intake_packet_state_machine.sql`
**Status:** implementation-ready, not yet executed against any environment.
**Scope of this note:** non-blocking deployment/operational risks identified during final implementation review. Does not restate the full review — see the migration's own header comments for what is DB-enforced vs. API-enforced. No DEC000001 rule was found stronger, weaker, or reopened by this migration.

## Non-blocking deployment risks

### 1. §1's precondition block is intentionally non-idempotent

Every other section of this migration (claim fields, supersession, archival, the two new tables, their triggers) is written to be safely re-run after a partial failure, using `ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`, `CREATE TABLE/INDEX IF NOT EXISTS`, `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER`, and `CREATE OR REPLACE FUNCTION`.

§1 (the `packet_status` four-state → six-state swap) is deliberately **not** written this way. It is a fail-loud precondition by design: it must find exactly one single-column `CHECK` constraint on `packet_status`, verify it looks like the legacy four-state definition, and only then drop and replace it — aborting loudly rather than guessing if the live schema doesn't match expectations.

**Consequence:** if §1 succeeds and a later statement in the file fails, a straight re-run of the whole file will abort at §1 every time afterward — it will correctly detect the six-state constraint already installed and raise the "may mean this migration already ran" exception, without ever reaching the idempotent recovery statements later in the file.

In practice this is only a real risk if the migration runner does **not** wrap the entire file in a single transaction (standard Supabase CLI / `psql -f` migration behavior does wrap each file in one transaction, in which case a failure anywhere rolls back everything, including §1, and this scenario cannot occur). Recommend confirming the actual deployment tooling wraps each migration file in one transaction before running this against a live environment. If it does not, manual recovery (temporarily commenting out §1 on a re-run) would be required after a partial failure that occurs after §1 commits.

### 2. Provenance of the active-user trigger requirement

Both new validation triggers (`validate_intake_packet_revision_actor`, `validate_intake_packet_event_actor`) reject an insert when the referenced `operations.users` row exists but `is_active = false`.

This requirement does **not** come from DEC000001's text — the decision record only establishes that `*_user_id`/`actor_id` fields must reference a stable user identifier, never a display-name snapshot (§7 item 6). The "must also be active" check traces to Brad's separate auth-stopgap approval earlier in the Phase 5 implementation thread ("validate that `X-User-Id` is a valid UUID, references an active `operations.users` record, and has the role required for the command"). Both are legitimately approved, but from two different governance inputs — flagged here so a future reader doesn't attribute the active-user check to DEC000001 itself.

### 3. User-referencing foreign keys have no `ON DELETE` clause

`claimed_by_user_id`, `archived_by_user_id`, and `actor_user_id` all reference `operations.users(user_id)` with the default `ON DELETE NO ACTION`. This matches the existing convention already used for user FKs in `004_operations_tables.sql` (users are deactivated via `is_active`, never hard-deleted) — noted here only for awareness, not a departure from repo convention.

## Mechanical cleanup applied (this pass)

- `intake_packet_events.event_type` and `.actor_type` CHECK constraints are now explicitly named (`intake_packet_events_event_type_check`, `intake_packet_events_actor_type_check`) instead of relying on Postgres's auto-generated names, for consistency with every other constraint in the file and to avoid a future "guess the name" situation.
- §1's two catalog queries no longer carry the redundant `att.attnum = ANY (con.conkey)` join condition — the exact single-column match (`con.conkey = ARRAY[att.attnum]::smallint[]`) in the `WHERE` clause already subsumes it. No behavior change; verified equivalent and re-parsed clean with `sqlfluff` (postgres dialect, 0 unparsable nodes).

## Verification performed

- `sqlfluff parse` (postgres dialect) on the full file: 0 unparsable nodes, both before and after this cleanup pass.
- Grep-confirmed zero remaining `att.attnum = ANY (con.conkey)` occurrences and presence of both new named constraints.
- Re-checked the mechanical edits against DEC000001 §5.8 (event type list, ten values, unchanged) and against the migration's own packet_status precondition logic (join simplification is logically equivalent to the prior form) — no semantic or policy change introduced by this cleanup pass.
