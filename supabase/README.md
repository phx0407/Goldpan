# GoldPan Supabase — Phase 1 Setup

## Prerequisites

- Active Supabase project (Settings → API to get URL + keys)
- `.env` file with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` set (see `.env.supabase.example`)
- Python 3.10+ with `supabase`, `gspread`, and `python-dotenv` installed:
  ```
  pip install supabase gspread python-dotenv
  ```

---

## Step 1 — Apply SQL migrations

Migrations must be applied **in order**. Each file is idempotent (`CREATE OR REPLACE`, `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`).

### Option A: Supabase SQL Editor (recommended for first run)

Open your project → **SQL Editor** and run each file in order:

1. `supabase/migrations/001_create_schemas.sql`
2. `supabase/migrations/002_evidence_tables.sql`
3. `supabase/migrations/003_knowledge_tables.sql`
4. `supabase/migrations/004_operations_tables.sql`
5. `supabase/migrations/005_rls_policies.sql`
6. `supabase/migrations/006_triggers.sql`
7. `supabase/migrations/007_views.sql`

Paste the contents of each file and click **Run**. Check for errors before proceeding to the next.

### Option B: Supabase CLI

```bash
supabase db push
```

Requires `supabase/config.toml` and a linked project (`supabase link --project-ref <ref>`).

---

## Step 2 — Verify schema

After applying all migrations, run this query in the SQL Editor to confirm all schemas and tables exist:

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('evidence', 'knowledge', 'operations', 'public')
  AND table_type = 'BASE TABLE'
ORDER BY table_schema, table_name;
```

Expected: ~18 base tables across the three application schemas.

Verify views:

```sql
SELECT table_schema, table_name
FROM information_schema.views
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected: `v_dishes`, `v_freshness`, `v_pipeline_status`, `v_restaurants`.

---

## Step 3 — Run the data migration (dry run first)

```bash
# Dry run — prints what would be written, writes nothing
python migrate_sheets_to_supabase.py

# Apply — writes to Supabase
python migrate_sheets_to_supabase.py --apply

# Apply + upsert on conflict (safe to re-run)
python migrate_sheets_to_supabase.py --apply --force
```

The script reads from Google Sheets (requires `GOOGLE_SERVICE_ACCOUNT_FILE`) and writes
to Supabase using the service role key (bypasses RLS).

Migration order (two-pass FK strategy):
1. `evidence.restaurants` — canonical entity, no FK deps
2. Fetch UUID map (`external_id` → `restaurant_id`)
3. `evidence.menu_sources` — inject `restaurant_id` FK
4. `evidence.dishes` — inject `restaurant_id` FK
5. Fetch dish UUID map
6. `evidence.ingredients` — inject `dish_id` + `restaurant_id` FKs
7. `knowledge.transparency_scores` — inject `dish_id` + `restaurant_id` FKs
8. `evidence.allergen_disclosures` — inject `dish_id` + `restaurant_id` FKs

---

## Step 4 — Verify data

```sql
-- Row counts
SELECT 'restaurants' AS t, COUNT(*) FROM evidence.restaurants
UNION ALL SELECT 'dishes',   COUNT(*) FROM evidence.dishes
UNION ALL SELECT 'ingredients', COUNT(*) FROM evidence.ingredients
UNION ALL SELECT 'transparency_scores', COUNT(*) FROM knowledge.transparency_scores;

-- Spot-check a dish via the output view
SELECT dish_name, restaurant_name, total_score, derived_filters
FROM public.v_dishes
LIMIT 5;
```

---

## Schema overview

| Schema        | Purpose                                      | Who writes         |
|---------------|----------------------------------------------|--------------------|
| `evidence`    | Durable, provenance-tracked human evidence   | canvasser / reviewer / coordinator / admin |
| `knowledge`   | Disposable, pipeline-computed conclusions    | `governance_engine` service role only |
| `operations`  | Users, audit log, jobs, feature flags        | system / admin     |
| `public`      | Read-only views for application output       | (views only)       |

---

## Architecture notes

- **Evidence/Knowledge boundary** is enforced by both RLS policies (`005_rls_policies.sql`) and
  database triggers (`006_triggers.sql`). The `governance_engine` service role is the only actor
  that may write to the `knowledge` schema.
- **lifecycle_events** is append-only. UPDATE and DELETE raise an exception (trigger + no RLS policy).
- **Allergen updates** require `SET LOCAL goldpan.change_reason = 'reason';` before any UPDATE
  on `evidence.allergen_disclosures` (GP-RULE-012).
- **restaurants** has no DELETE policy — use `lifecycle_status = 'deactivated'` instead.
- **total_score** in `knowledge.transparency_scores` is a `GENERATED ALWAYS AS` column; never set it directly.

See `docs/BACKEND_MASTER_OS_VISION.md` for the full architecture and phased implementation plan.
