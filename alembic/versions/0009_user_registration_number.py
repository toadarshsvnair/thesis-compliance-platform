"""Add User.registration_number -- like programme/faculty, this moves from
being re-typed on every submission upload to being a property of the
student's account, set once when an admin creates it. Lets a student's
upload flow skip asking for their own name/registration number entirely."""
from alembic import op
import sqlalchemy as sa

revision = "0009_user_registration_number"
down_revision = "0008_faculty_reference_style"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("registration_number", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("users", "registration_number")
