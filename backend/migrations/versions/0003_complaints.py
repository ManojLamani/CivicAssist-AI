"""Store citizen complaint submissions."""

import sqlalchemy as sa
from alembic import op

revision = "0003_complaints"
down_revision = "0002_login_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "complaints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("location", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "submission_id", name="uq_complaints_user_submission"),
        sa.CheckConstraint("char_length(btrim(title)) >= 5", name="ck_complaints_title"),
        sa.CheckConstraint(
            "char_length(btrim(description)) BETWEEN 10 AND 5000", name="ck_complaints_description"
        ),
        sa.CheckConstraint("char_length(btrim(location)) >= 5", name="ck_complaints_location"),
        sa.CheckConstraint(
            "category IN ('roads', 'garbage', 'water_supply', 'drainage', "
            "'streetlights', 'public_infrastructure', 'sanitation', 'other')",
            name="ck_complaints_category",
        ),
        sa.CheckConstraint("status = 'submitted'", name="ck_complaints_status"),
    )


def downgrade():
    op.drop_table("complaints")
