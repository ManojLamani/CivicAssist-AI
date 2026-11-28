"""Create identity and department tables and enable PostGIS."""

import sqlalchemy as sa
from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public")
    roles = op.create_table(
        "roles",
        sa.Column("name", sa.String(32), primary_key=True),
        sa.CheckConstraint(
            "name IN ('citizen', 'administrator', 'department_operator')",
            name="ck_roles_name",
        ),
    )
    op.bulk_insert(
        roles, [{"name": "citizen"}, {"name": "administrator"}, {"name": "department_operator"}]
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role_name",
            sa.String(32),
            sa.ForeignKey("roles.name"),
            nullable=False,
            server_default="citizen",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("email = lower(btrim(email)) AND email <> ''", name="ck_users_email"),
        sa.CheckConstraint("btrim(full_name) <> ''", name="ck_users_full_name"),
        sa.CheckConstraint("password_hash <> ''", name="ck_users_password_hash"),
    )
    op.create_index("ix_users_role_name", "users", ["role_name"])
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("city", "name", name="uq_departments_city_name"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_departments_name"),
        sa.CheckConstraint("btrim(city) <> ''", name="ck_departments_city"),
    )
    op.create_table(
        "department_operators",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "department_id",
            sa.Uuid(),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_department_operators_department_id", "department_operators", ["department_id"]
    )


def downgrade():
    op.drop_table("department_operators")
    op.drop_table("departments")
    op.drop_table("users")
    op.drop_table("roles")
    # PostGIS may be shared by other applications; retain the extension on rollback.
