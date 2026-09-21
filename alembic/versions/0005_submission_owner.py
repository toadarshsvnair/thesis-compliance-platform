"""Add Submission.owner_user_id so a student's own submissions can actually
be scoped to them -- previously the student role was unconditionally denied
access to any submission at all, since there was no ownership mapping."""
from alembic import op
import sqlalchemy as sa

revision = "0005_submission_owner"
down_revision = "0004_auth_and_source_reference"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("submissions", sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_submissions_owner_user_id", "submissions", ["owner_user_id"])


def downgrade():
    op.drop_index("ix_submissions_owner_user_id", table_name="submissions")
    op.drop_column("submissions", "owner_user_id")
