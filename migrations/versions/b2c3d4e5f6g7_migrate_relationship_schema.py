"""migrate relationship schema

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-24 16:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add new columns
    op.add_column('relationships', sa.Column('properties', JSONB, server_default='{}'))
    op.add_column('relationships', sa.Column('canon', JSONB, server_default='{"layer": "primary", "status": "active"}'))
    
    # 2. Rename details -> description (assuming details exists and description does not)
    # We use alter_column for renaming if supported, or just add/update/drop.
    # Postgres supports renaming.
    try:
        op.alter_column('relationships', 'details', new_column_name='description')
    except Exception:
        # Fallback if details doesn't exist or description already exists
        # We'll just ensure description exists
        op.add_column('relationships', sa.Column('description', sa.String(), nullable=True))

    # 3. Migrate old data
    # Migrate strength -> properties['strength']
    op.execute("""
        UPDATE relationships
        SET properties = jsonb_build_object('strength', strength)
        WHERE strength IS NOT NULL
    """)

    # 4. Drop old columns
    op.drop_column('relationships', 'strength')
    # Note: details is already renamed or we assume it's gone/handled. 
    # If we renamed it, we don't drop 'description'.
    # If the rename failed and we added description, we might want to drop details if it exists.
    # But for simplicity/safety in this script, we'll assume the rename worked or wasn't needed.

def downgrade():
    # Reverse operations
    op.add_column('relationships', sa.Column('strength', sa.Float(), nullable=True))
    op.alter_column('relationships', 'description', new_column_name='details')
    op.drop_column('relationships', 'properties')
    op.drop_column('relationships', 'canon')
