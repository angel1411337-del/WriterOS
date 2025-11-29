"""add pgvector indexes

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2025-11-24 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Entities
    op.create_index('ix_entities_embedding', 'entities', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    
    # Facts
    op.create_index('ix_facts_embedding', 'facts', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    
    # Events
    op.create_index('ix_events_embedding', 'events', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    
    # Scenes
    op.create_index('ix_scenes_embedding', 'scenes', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    
    # Documents
    op.create_index('ix_documents_embedding', 'documents', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})


def downgrade() -> None:
    op.drop_index('ix_documents_embedding', table_name='documents', postgresql_using='hnsw')
    op.drop_index('ix_scenes_embedding', table_name='scenes', postgresql_using='hnsw')
    op.drop_index('ix_events_embedding', table_name='events', postgresql_using='hnsw')
    op.drop_index('ix_facts_embedding', table_name='facts', postgresql_using='hnsw')
    op.drop_index('ix_entities_embedding', table_name='entities', postgresql_using='hnsw')
