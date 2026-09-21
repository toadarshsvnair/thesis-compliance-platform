"""Add Faculty.reference_style -- each faculty's required citation style
(APA, Chicago Author-Date, or APA/Bluebook), used as a new compliance
checkpoint on reference-list formatting."""
from alembic import op
import sqlalchemy as sa

revision = "0008_faculty_reference_style"
down_revision = "0007_user_programme_faculty"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("faculties", sa.Column("reference_style", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("faculties", "reference_style")
