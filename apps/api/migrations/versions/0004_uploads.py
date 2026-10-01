"""Retained image blobs and publication references."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_uploads_owner_id", "uploads", ["owner_id"])
    for table, column, constraint in (
        ("users", "avatar_id", "fk_user_avatar"),
        ("app_drafts", "cover_id", "fk_draft_cover"),
        ("app_versions", "cover_id", "fk_version_cover"),
    ):
        op.add_column(table, sa.Column(column, sa.Uuid()))
        op.create_foreign_key(constraint, table, "uploads", [column], ["id"])
    op.create_table(
        "upload_references",
        sa.Column("upload_id", sa.Uuid(), sa.ForeignKey("uploads.id"), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("app_versions.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("upload_references")
    for table, column, constraint in (
        ("app_versions", "cover_id", "fk_version_cover"),
        ("app_drafts", "cover_id", "fk_draft_cover"),
        ("users", "avatar_id", "fk_user_avatar"),
    ):
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.drop_column(table, column)
    op.drop_table("uploads")
