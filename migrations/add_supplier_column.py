"""
Add supplier column to transactions table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_supplier_column'
down_revision = 'previous_revision_id'  # Replace with actual previous revision ID
branch_labels = None
depends_on = None

def upgrade():
    # Add supplier column to transactions table
    op.add_column('transactions', sa.Column('supplier', sa.String(length=100), nullable=True))

def downgrade():
    # Remove supplier column from transactions table
    op.drop_column('transactions', 'supplier')
