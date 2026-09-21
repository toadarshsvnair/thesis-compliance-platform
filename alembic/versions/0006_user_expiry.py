"""Add User.expires_at for time-limited accounts (part of admin user
management: create/edit/suspend/delete/reset-password, plus an optional
account end date)."""
from alembic import op
import sqlalchemy as sa

revision = "0006_user_expiry"
down_revision = "0005_submission_owner"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "expires_at")
