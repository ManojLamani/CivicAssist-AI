"""Enable status transitions and append-only status history."""

import sqlalchemy as sa
from alembic import op

revision = "0004_status_history"
down_revision = "0003_complaints"
branch_labels = None
depends_on = None

STATUSES = "('submitted', 'acknowledged', 'in_progress', 'resolved', 'closed')"


def upgrade():
    op.drop_constraint("ck_complaints_status", "complaints", type_="check")
    op.create_check_constraint("ck_complaints_status", "complaints", f"status IN {STATUSES}")
    op.create_table(
        "complaint_status_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "complaint_id",
            sa.Uuid(),
            sa.ForeignKey("complaints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(f"to_status IN {STATUSES}", name="ck_status_history_to_status"),
        sa.CheckConstraint(f"from_status IN {STATUSES}", name="ck_status_history_from_status"),
        sa.CheckConstraint("char_length(btrim(note)) >= 1", name="ck_status_history_note"),
    )
    op.create_index(
        "ix_complaint_status_history_complaint_id", "complaint_status_history", ["complaint_id"]
    )
    op.execute("""
        INSERT INTO complaint_status_history
            (complaint_id, actor_id, from_status, to_status, note, created_at)
        SELECT id, user_id, NULL, status, 'Complaint submitted.', created_at FROM complaints
    """)
    op.execute("""
        CREATE FUNCTION protect_complaint_status_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE parent_exists boolean;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                EXECUTE format(
                    'SELECT EXISTS (SELECT 1 FROM %I.complaints WHERE id = $1)', TG_TABLE_SCHEMA)
                    INTO parent_exists USING OLD.complaint_id;
                IF NOT parent_exists THEN RETURN OLD; END IF;
            END IF;
            RAISE EXCEPTION 'Complaint status history is append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER complaint_status_history_append_only
        BEFORE UPDATE OR DELETE ON complaint_status_history
        FOR EACH ROW EXECUTE FUNCTION protect_complaint_status_history()
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM complaints WHERE status <> 'submitted') THEN
                RAISE EXCEPTION 'Cannot downgrade: complaints have progressed beyond submitted';
            END IF;
        END $$
    """)
    op.drop_table("complaint_status_history")
    op.execute("DROP FUNCTION protect_complaint_status_history()")
    op.drop_constraint("ck_complaints_status", "complaints", type_="check")
    op.create_check_constraint("ck_complaints_status", "complaints", "status = 'submitted'")
