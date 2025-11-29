"""add conflict model

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-11-24 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None

def upgrade():
    # Create conflicts table
    op.create_table('conflicts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('vault_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('conflict_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('intensity', sa.Integer(), nullable=False),
        sa.Column('stakes', sa.String(), nullable=False),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('canon', JSONB, server_default='{"layer": "primary"}', nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for conflicts
    op.create_index(op.f('ix_conflicts_vault_id'), 'conflicts', ['vault_id'], unique=False)
    op.create_index(op.f('ix_conflicts_conflict_type'), 'conflicts', ['conflict_type'], unique=False)
    op.create_index(op.f('ix_conflicts_status'), 'conflicts', ['status'], unique=False)
    
    # HNSW Index for embedding
    op.create_index('ix_conflicts_embedding', 'conflicts', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})

    # Create conflict_participants table
    op.create_table('conflict_participants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('conflict_id', sa.UUID(), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('outcome', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['conflict_id'], ['conflicts.id'], ),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ),
        sa.PrimaryKeyConstraint('conflict_id', 'entity_id')
    )

def downgrade():
    op.drop_table('conflict_participants')
    op.drop_index('ix_conflicts_embedding', table_name='conflicts', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index(op.f('ix_conflicts_status'), table_name='conflicts')
    op.drop_index(op.f('ix_conflicts_conflict_type'), table_name='conflicts')
    op.drop_index(op.f('ix_conflicts_vault_id'), table_name='conflicts')
    op.drop_table('conflicts')
