# Migration: add_tenant_system
# Adds the tenants table and wires tenant_id into every business table.
# All existing rows are backfilled to the 'default' tenant before the
# NOT NULL constraint is applied — no data is lost.

import uuid
from django.db import migrations, models


# ---------------------------------------------------------------------------
# SQL: Steps 2–5  (tenants table itself is created by CreateModel above)
# ---------------------------------------------------------------------------

SQL_FORWARD = """
-- =================================================================
-- STEP 2: Insert the default tenant
-- =================================================================
INSERT INTO tenants (id, slug, name, plan, status, config, created_at)
VALUES (
    gen_random_uuid(),
    'default',
    'Default Workspace',
    'starter',
    'active',
    '{
        "branding": {
            "primary_color": "#D05F3B",
            "company_name": "My Catering Co."
        },
        "locale": {
            "currency": "INR",
            "currency_symbol": "\u20b9",
            "timezone": "Asia/Kolkata",
            "date_format": "DD/MM/YYYY"
        },
        "tax": {
            "type": "GST",
            "rates": [
                {"label": "CGST", "rate": 9},
                {"label": "SGST", "rate": 9}
            ]
        },
        "features": {
            "crm": true,
            "online_payments": false,
            "whatsapp_notifications": false
        }
    }'::jsonb,
    now()
);

-- =================================================================
-- STEP 3: Add tenant_id to every business table
--         Pattern per table:
--           1. ADD COLUMN (nullable FK)
--           2. UPDATE  → backfill all rows to 'default' tenant
--           3. ALTER   → enforce NOT NULL
--           4. CREATE INDEX (tenant_id, created_at DESC)
-- =================================================================

-- ---- users ----
ALTER TABLE users
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE users
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE users
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_users_tenant
    ON users(tenant_id, created_at DESC);

-- ---- events ----
ALTER TABLE events
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE events
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE events
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_events_tenant
    ON events(tenant_id, created_at DESC);

-- ---- inquiries ----
ALTER TABLE inquiries
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE inquiries
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE inquiries
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_inquiries_tenant
    ON inquiries(tenant_id, created_at DESC);

-- ---- quotations ----
ALTER TABLE quotations
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE quotations
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE quotations
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_quotations_tenant
    ON quotations(tenant_id, created_at DESC);

-- ---- ingredients ----
ALTER TABLE ingredients
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE ingredients
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE ingredients
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_ingredients_tenant
    ON ingredients(tenant_id, created_at DESC);

-- ---- dishes ----
ALTER TABLE dishes
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE dishes
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE dishes
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_dishes_tenant
    ON dishes(tenant_id, created_at DESC);

-- ---- dish_recipes ----
ALTER TABLE dish_recipes
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE dish_recipes
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE dish_recipes
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_dish_recipes_tenant
    ON dish_recipes(tenant_id, created_at DESC);

-- ---- event_menu_items ----
ALTER TABLE event_menu_items
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE event_menu_items
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE event_menu_items
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_event_menu_items_tenant
    ON event_menu_items(tenant_id, created_at DESC);

-- ---- event_ingredients  (no created_at — uses calculated_at) ----
ALTER TABLE event_ingredients
    ADD COLUMN tenant_id UUID REFERENCES tenants(id);

UPDATE event_ingredients
    SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE event_ingredients
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX idx_event_ingredients_tenant
    ON event_ingredients(tenant_id, calculated_at DESC);

-- =================================================================
-- STEP 4: Replace UNIQUE(email) with UNIQUE(tenant_id, email)
--         on the users table so the same email can exist across
--         different tenants.
-- =================================================================

-- Drop the existing single-column unique on users.email so we can replace it
-- with UNIQUE(tenant_id, email).  Django may create this as either a UNIQUE
-- CONSTRAINT (backed by an index) or a standalone unique index — handle both.
DO $$
DECLARE
    r RECORD;
BEGIN
    -- 1. Drop UNIQUE CONSTRAINTS on just the email column.
    --    Dropping the constraint automatically drops the backing index.
    FOR r IN
        SELECT c.conname
        FROM   pg_constraint c
        JOIN   pg_class      t  ON c.conrelid = t.oid
        WHERE  t.relname           = 'users'
          AND  c.contype           = 'u'
          AND  array_length(c.conkey, 1) = 1
          AND  (SELECT attname
                FROM   pg_attribute
                WHERE  attrelid = t.oid
                  AND  attnum   = c.conkey[1]) = 'email'
    LOOP
        EXECUTE format('ALTER TABLE users DROP CONSTRAINT IF EXISTS %I', r.conname);
    END LOOP;

    -- 2. Drop any remaining standalone unique INDEXES on just email
    --    (not backed by a constraint — those were handled above).
    FOR r IN
        SELECT i.relname AS idx_name
        FROM   pg_index    ix
        JOIN   pg_class    t  ON t.oid  = ix.indrelid
        JOIN   pg_class    i  ON i.oid  = ix.indexrelid
        JOIN   pg_attribute a ON a.attrelid = t.oid
                              AND a.attnum   = ANY(ix.indkey)
        WHERE  t.relname         = 'users'
          AND  ix.indisunique    = true
          AND  ix.indisprimary   = false
          AND  a.attname         = 'email'
          AND  array_length(ix.indkey, 1) = 1
          AND  NOT EXISTS (
                   SELECT 1 FROM pg_constraint c
                   WHERE  c.conindid = ix.indexrelid
               )
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', r.idx_name);
    END LOOP;
END $$;

ALTER TABLE users
    ADD CONSTRAINT users_tenant_email_unique UNIQUE (tenant_id, email);

-- =================================================================
-- STEP 5: Enable Row Level Security on every business table
-- =================================================================

ALTER TABLE users              ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE events             ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON events
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE inquiries          ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inquiries
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE quotations         ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON quotations
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE ingredients        ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ingredients
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE dishes             ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON dishes
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE dish_recipes       ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON dish_recipes
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE event_menu_items   ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON event_menu_items
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE event_ingredients  ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON event_ingredients
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
"""

SQL_REVERSE = """
-- Tear down RLS
DROP POLICY IF EXISTS tenant_isolation ON event_ingredients;
ALTER TABLE event_ingredients  DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON event_menu_items;
ALTER TABLE event_menu_items   DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON dish_recipes;
ALTER TABLE dish_recipes       DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON dishes;
ALTER TABLE dishes             DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON ingredients;
ALTER TABLE ingredients        DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON quotations;
ALTER TABLE quotations         DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON inquiries;
ALTER TABLE inquiries          DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON events;
ALTER TABLE events             DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON users;
ALTER TABLE users              DISABLE ROW LEVEL SECURITY;

-- Remove composite unique; restore single-column unique on email
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_email_unique;
ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);

-- Remove indexes
DROP INDEX IF EXISTS idx_event_ingredients_tenant;
DROP INDEX IF EXISTS idx_event_menu_items_tenant;
DROP INDEX IF EXISTS idx_dish_recipes_tenant;
DROP INDEX IF EXISTS idx_dishes_tenant;
DROP INDEX IF EXISTS idx_ingredients_tenant;
DROP INDEX IF EXISTS idx_quotations_tenant;
DROP INDEX IF EXISTS idx_inquiries_tenant;
DROP INDEX IF EXISTS idx_events_tenant;
DROP INDEX IF EXISTS idx_users_tenant;

-- Remove tenant_id columns
ALTER TABLE event_ingredients DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE event_menu_items  DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE dish_recipes      DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE dishes            DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE ingredients       DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE quotations        DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE inquiries         DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE events            DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE users             DROP COLUMN IF EXISTS tenant_id;

-- Remove default tenant row
DELETE FROM tenants WHERE slug = 'default';
"""


class Migration(migrations.Migration):

    initial = True

    # This migration must run AFTER all existing app migrations so the
    # business tables already exist when we add tenant_id columns to them.
    dependencies = [
        ('authentication', '0001_initial'),
        ('events',         '0002_event_add_fields'),
        ('inquiries',      '0005_inquiry_email'),
        ('quotations',     '0001_initial'),
        ('master',         '0004_add_meat_subcategories'),
        ('menu',           '0002_eventmenuitem_quantity_unit'),
        ('engine',         '0002_alter_eventingredient_total_quantity'),
    ]

    operations = [
        # ------------------------------------------------------------------
        # STEP 1: Create the tenants table (Django manages the DDL)
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id',            models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('slug',          models.SlugField(max_length=100, unique=True)),
                ('name',          models.CharField(max_length=255)),
                ('plan',          models.CharField(max_length=20, default='starter')),
                ('status',        models.CharField(max_length=20, default='active')),
                ('config',        models.JSONField(default=dict)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
                ('trial_ends_at', models.DateTimeField(null=True, blank=True)),
            ],
            options={'db_table': 'tenants'},
        ),

        # ------------------------------------------------------------------
        # STEPS 2–5: Insert default tenant, backfill + constrain all tables,
        #            add composite unique, enable RLS with tenant policies.
        # ------------------------------------------------------------------
        migrations.RunSQL(
            sql=SQL_FORWARD,
            reverse_sql=SQL_REVERSE,
        ),
    ]
