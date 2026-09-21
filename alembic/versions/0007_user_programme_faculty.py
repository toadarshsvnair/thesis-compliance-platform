"""Add User.programme and User.faculty_id -- these move from being re-typed
on every submission upload to being a property of the student's account,
set once when an admin creates it."""
from alembic import op
import sqlalchemy as sa

revision = "0007_user_programme_faculty"
down_revision = "0006_user_expiry"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("programme", sa.String(250), nullable=True))
    op.add_column("users", sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculties.id"), nullable=True))


def downgrade():
    op.drop_column("users", "faculty_id")
    op.drop_column("users", "programme")
