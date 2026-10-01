"""Replace skeleton metadata with published versions and pinned answers."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Retire only the original ownerless skeleton fixture; seed recreates its published version.
    op.execute("""
        DELETE FROM learning_apps
        WHERE id = '00000000-0000-4000-8000-000000000001' AND owner_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM app_drafts WHERE app_id = learning_apps.id)
    """)
    op.alter_column("learning_apps", "owner_id", nullable=False)
    op.drop_column("learning_apps", "name")
    op.create_table(
        "app_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("app_id", sa.Uuid(), sa.ForeignKey("learning_apps.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("app_type", sa.String(16), nullable=False),
        sa.Column("strategy", sa.String(16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(64), nullable=False),
        sa.UniqueConstraint("app_id", "sequence", name="uq_app_version_sequence"),
    )
    op.create_index("ix_app_versions_app_id", "app_versions", ["app_id"])
    op.add_column("learning_apps", sa.Column("active_version_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_apps_active_version", "learning_apps", "app_versions", ["active_version_id"], ["id"]
    )
    op.create_table(
        "publication_reviews",
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("app_versions.id"), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("app_id", sa.Uuid(), sa.ForeignKey("learning_apps.id"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("app_versions.id"), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_snapshot", sa.JSON()),
        sa.Column("hidden_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_answer_owner_key"),
    )
    for column in ("owner_id", "app_id", "version_id"):
        op.create_index(f"ix_answers_{column}", "answers", [column])
    op.execute("""
        CREATE FUNCTION reject_version_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Published version content is immutable'; END $$
    """)
    op.execute("""
        CREATE TRIGGER immutable_version BEFORE UPDATE ON app_versions
        FOR EACH ROW EXECUTE FUNCTION reject_version_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER immutable_version ON app_versions")
    op.execute("DROP FUNCTION reject_version_mutation()")
    op.drop_table("answers")
    op.drop_table("publication_reviews")
    op.drop_constraint("fk_apps_active_version", "learning_apps", type_="foreignkey")
    op.drop_column("learning_apps", "active_version_id")
    op.drop_table("app_versions")
    op.add_column(
        "learning_apps", sa.Column("name", sa.String(120), nullable=False, server_default="")
    )
    op.alter_column("learning_apps", "name", server_default=None)
    op.alter_column("learning_apps", "owner_id", nullable=True)
