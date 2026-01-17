"""Initial schema with pgvector extension

Revision ID: 001
Revises:
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start', sa.DateTime(), nullable=False),
        sa.Column('end', sa.DateTime(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=False, server_default='google'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id')
    )
    op.create_index(op.f('ix_events_external_id'), 'events', ['external_id'], unique=True)
    op.create_index(op.f('ix_events_start'), 'events', ['start'], unique=False)
    op.create_index(op.f('ix_events_user_id'), 'events', ['user_id'], unique=False)

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('doc_type', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_doc_type'), 'documents', ['doc_type'], unique=False)
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)

    # Create embeddings table with vector column
    # First create the table without the vector column
    op.create_table(
        'embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE')
    )
    # Add vector column using raw SQL
    op.execute('ALTER TABLE embeddings ADD COLUMN embedding vector(384)')

    op.create_index(op.f('ix_embeddings_document_id'), 'embeddings', ['document_id'], unique=False)
    op.create_index(op.f('ix_embeddings_model_version'), 'embeddings', ['model_version'], unique=False)

    # Create ivfflat index for vector similarity search
    # Note: ivfflat requires building lists after data is inserted
    op.execute("""
        CREATE INDEX IF NOT EXISTS embeddings_embedding_idx
        ON embeddings USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Create rules table
    op.create_table(
        'rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('conditions', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rules_rule_type'), 'rules', ['rule_type'], unique=False)
    op.create_index(op.f('ix_rules_user_id'), 'rules', ['user_id'], unique=False)

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trace_id', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        sa.Column('target_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='success'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_action_type'), 'audit_log', ['action_type'], unique=False)
    op.create_index(op.f('ix_audit_log_trace_id'), 'audit_log', ['trace_id'], unique=False)
    op.create_index(op.f('ix_audit_log_user_id'), 'audit_log', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index(op.f('ix_audit_log_user_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_trace_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action_type'), table_name='audit_log')
    op.drop_table('audit_log')

    op.drop_index(op.f('ix_rules_user_id'), table_name='rules')
    op.drop_index(op.f('ix_rules_rule_type'), table_name='rules')
    op.drop_table('rules')

    # Drop vector index
    op.drop_index('embeddings_embedding_idx', table_name='embeddings')
    op.drop_index(op.f('ix_embeddings_model_version'), table_name='embeddings')
    op.drop_index(op.f('ix_embeddings_document_id'), table_name='embeddings')
    op.drop_table('embeddings')

    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_doc_type'), table_name='documents')
    op.drop_table('documents')

    op.drop_index(op.f('ix_events_user_id'), table_name='events')
    op.drop_index(op.f('ix_events_start'), table_name='events')
    op.drop_index(op.f('ix_events_external_id'), table_name='events')
    op.drop_table('events')

    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
