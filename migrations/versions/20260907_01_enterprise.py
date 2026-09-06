"""Add enterprise tables without modifying the legacy OCR schema."""
from alembic import op
from enterprise.database import Base
revision = '20260907_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind(), checkfirst=False)


def downgrade():
    # Explicit rollback only; this drops enterprise data, never legacy tables.
    Base.metadata.drop_all(op.get_bind(), checkfirst=True)
