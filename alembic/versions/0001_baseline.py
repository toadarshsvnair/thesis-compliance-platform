"""Baseline schema for Thesis Compliance Platform v0.9.

This migration intentionally derives the initial schema from SQLAlchemy metadata.
Future schema changes should be generated with `alembic revision --autogenerate`
and reviewed before deployment.
"""
from alembic import op
from app.db import Base
from app import models  # noqa: F401

revision="0001_baseline"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind())

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
