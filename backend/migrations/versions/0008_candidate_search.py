"""Candidate search, pgvector/FTS and tenant query cache.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    # Deliberately fail migration if the deployment lacks pgvector. Do not ship
    # a schema that claims semantic search but silently has no vector operator.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("ALTER TABLE candidates ADD COLUMN years_experience_total double precision")
    op.execute("ALTER TABLE candidates ADD COLUMN experience_computed_at timestamptz")
    op.execute(
        "GRANT UPDATE(years_experience_total,experience_computed_at) ON candidates TO hr_app"
    )
    op.execute("""
        CREATE TABLE candidate_search_docs (
            candidate_id uuid PRIMARY KEY,
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            search_text text NOT NULL,
            normalized_name text NOT NULL,
            content_hash text NOT NULL,
            embedding vector,
            embedding_model text NOT NULL DEFAULT '',
            embedding_dimensions integer NOT NULL DEFAULT 1536,
            embedding_status text NOT NULL DEFAULT 'unavailable',
            updated_at timestamptz NOT NULL DEFAULT now(),
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', search_text)) STORED,
            FOREIGN KEY(org_id,candidate_id) REFERENCES candidates(org_id,id) ON DELETE CASCADE,
            CHECK (embedding IS NULL OR vector_dims(embedding)=embedding_dimensions)
        )
    """)
    op.execute("CREATE INDEX search_docs_org ON candidate_search_docs(org_id)")
    op.execute("CREATE INDEX search_docs_tsv ON candidate_search_docs USING gin(tsv)")
    op.execute("""CREATE INDEX search_docs_name ON candidate_search_docs
                  USING gin(normalized_name gin_trgm_ops)""")
    # Dimensionless storage permits configurable providers without relabeling
    # old vectors. Default 1536-d deployment gets an actual HNSW expression index.
    op.execute("""CREATE INDEX search_docs_hnsw_1536 ON candidate_search_docs
        USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
        WHERE embedding_dimensions=1536 AND embedding IS NOT NULL""")
    op.execute("""CREATE TABLE search_query_cache (
        org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        query_key text NOT NULL, dsl jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(org_id,query_key))""")
    # Python backfill shares ingestion's conservative arithmetic and normalization;
    # it does NOT make provider calls during schema deployment.
    import hashlib
    from datetime import UTC, datetime

    from app.search_documents import document, experience, normalize

    conn = op.get_bind()
    for row in conn.execute(
        sa.text("SELECT id,org_id,full_name,profile FROM candidates")
    ).mappings():
        profile = row["profile"] or {}
        text = document(profile, row["full_name"])
        conn.execute(
            sa.text("""UPDATE candidates SET years_experience_total=:years,
                     experience_computed_at=:now WHERE id=:id"""),
            {"id": row["id"], "years": experience(profile), "now": datetime.now(UTC)},
        )
        conn.execute(
            sa.text("""INSERT INTO candidate_search_docs
            (candidate_id,org_id,search_text,normalized_name,content_hash)
            VALUES (:id,:org,:text,:name,:hash)"""),
            {
                "id": row["id"],
                "org": row["org_id"],
                "text": text,
                "name": normalize(row["full_name"]),
                "hash": hashlib.sha256(text.encode()).hexdigest(),
            },
        )
    for table in ("candidate_search_docs", "search_query_cache"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table} FOR ALL TO hr_app
            USING (org_id=(select nullif(current_setting('app.current_org_id',true),'')::uuid))
            WITH CHECK (org_id=(select
                nullif(current_setting('app.current_org_id',true),'')::uuid))""")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO hr_app")


def downgrade():
    op.execute("DROP TABLE search_query_cache, candidate_search_docs")
    op.execute("ALTER TABLE candidates DROP COLUMN experience_computed_at")
    op.execute("ALTER TABLE candidates DROP COLUMN years_experience_total")
