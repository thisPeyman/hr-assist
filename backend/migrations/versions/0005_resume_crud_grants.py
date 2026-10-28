"""Allow tenant-scoped resume removal from the HR workspace.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("grant delete on resume_files to hr_app")
    op.execute("grant delete on candidates to hr_app")


def downgrade() -> None:
    op.execute("revoke delete on candidates from hr_app")
    op.execute("revoke delete on resume_files from hr_app")
