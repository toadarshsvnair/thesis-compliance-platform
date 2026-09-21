"""Add User.password_hash (real login) and Finding.source_reference (guideline
reference persisted for the evaluation report, previously discarded)."""
from alembic import op
import sqlalchemy as sa

revision = "0004_auth_and_source_reference"
down_revision = "0003_document_object_uri"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(length=200), nullable=True))
    op.add_column("findings", sa.Column("source_reference", sa.String(length=300), nullable=True))


def downgrade():
    op.drop_column("findings", "source_reference")
    op.drop_column("users", "password_hash")
