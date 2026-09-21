"""Store immutable object-storage URI for document versions."""
from alembic import op
import sqlalchemy as sa
revision = "0003_document_object_uri"
down_revision = "0002_processing_jobs"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("document_versions", sa.Column("object_uri", sa.String(length=1200), nullable=True))

def downgrade():
    op.drop_column("document_versions", "object_uri")
