"""Add asynchronous processing job state."""
from alembic import op
import sqlalchemy as sa
revision = "0002_processing_jobs"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(length=120), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_processing_jobs_job_id", "processing_jobs", ["job_id"], unique=True)
    op.create_index("ix_processing_jobs_submission_id", "processing_jobs", ["submission_id"])
    op.create_index("ix_processing_jobs_version_id", "processing_jobs", ["version_id"])

def downgrade():
    op.drop_index("ix_processing_jobs_version_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_submission_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_job_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
