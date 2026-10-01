"""Add accounts, hashed sessions, throttling and owned drafts."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "login_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("learning_apps", sa.Column("owner_id", sa.Uuid()))
    op.add_column("learning_apps", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_foreign_key("fk_learning_apps_owner", "learning_apps", "users", ["owner_id"], ["id"])
    op.create_index("ix_learning_apps_owner_id", "learning_apps", ["owner_id"])
    op.create_table(
        "app_drafts",
        sa.Column("app_id", sa.Uuid(), sa.ForeignKey("learning_apps.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("app_type", sa.String(16), nullable=False),
        sa.Column("strategy", sa.String(16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_drafts")
    op.drop_index("ix_learning_apps_owner_id", table_name="learning_apps")
    op.drop_constraint("fk_learning_apps_owner", "learning_apps", type_="foreignkey")
    op.drop_column("learning_apps", "deleted_at")
    op.drop_column("learning_apps", "owner_id")
    op.drop_table("login_buckets")
    op.drop_table("sessions")
    op.drop_table("users")
