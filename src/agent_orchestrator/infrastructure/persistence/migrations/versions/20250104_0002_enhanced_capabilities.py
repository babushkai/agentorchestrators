"""Enhanced capabilities - memory, sessions, file attachments

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension for semantic search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enum types
    op.execute("CREATE TYPE memory_type AS ENUM ('conversation', 'fact', 'summary', 'context', 'instruction')")
    op.execute("CREATE TYPE session_status AS ENUM ('active', 'paused', 'closed', 'expired')")

    # Create agent_memories table for long-term memory with vector embeddings
    op.create_table(
        'agent_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('memory_type', postgresql.ENUM(
            'conversation', 'fact', 'summary', 'context', 'instruction',
            name='memory_type', create_type=False
        ), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        # Vector embedding for semantic search (1536 dimensions for OpenAI embeddings)
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['agent_id'], ['agent_definitions.id'],
            name='fk_agent_memories_agent_id', ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_agent_memories')
    )
    op.create_index('ix_agent_memories_agent_id', 'agent_memories', ['agent_id'])
    op.create_index('ix_agent_memories_session_id', 'agent_memories', ['session_id'])
    op.create_index('ix_agent_memories_memory_type', 'agent_memories', ['memory_type'])
    op.create_index('ix_agent_memories_importance', 'agent_memories', ['importance_score'])
    op.create_index('ix_agent_memories_created_at', 'agent_memories', ['created_at'])

    # Create conversation_sessions table
    op.create_table(
        'conversation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('status', postgresql.ENUM(
            'active', 'paused', 'closed', 'expired',
            name='session_status', create_type=False
        ), nullable=False, server_default='active'),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('system_prompt_override', sa.Text(), nullable=True),
        sa.Column('max_history_messages', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['agent_id'], ['agent_definitions.id'],
            name='fk_conversation_sessions_agent_id', ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_conversation_sessions')
    )
    op.create_index('ix_conversation_sessions_agent_id', 'conversation_sessions', ['agent_id'])
    op.create_index('ix_conversation_sessions_tenant_id', 'conversation_sessions', ['tenant_id'])
    op.create_index('ix_conversation_sessions_status', 'conversation_sessions', ['status'])
    op.create_index('ix_conversation_sessions_last_activity', 'conversation_sessions', ['last_activity_at'])

    # Create conversation_messages table (stores full message history)
    op.create_table(
        'conversation_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),  # user, assistant, system, tool
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),  # for tool messages
        sa.Column('tool_call_id', sa.String(100), nullable=True),
        sa.Column('tool_calls', postgresql.JSONB(), nullable=True),  # for assistant tool calls
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['session_id'], ['conversation_sessions.id'],
            name='fk_conversation_messages_session_id', ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_conversation_messages')
    )
    op.create_index('ix_conversation_messages_session_id', 'conversation_messages', ['session_id'])
    op.create_index('ix_conversation_messages_created_at', 'conversation_messages', ['created_at'])

    # Create file_attachments table
    op.create_table(
        'file_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=True),  # SHA-256
        sa.Column('parsed_content', sa.Text(), nullable=True),  # Extracted text content
        sa.Column('parse_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['task_id'], ['tasks.id'],
            name='fk_file_attachments_task_id', ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['session_id'], ['conversation_sessions.id'],
            name='fk_file_attachments_session_id', ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_file_attachments')
    )
    op.create_index('ix_file_attachments_task_id', 'file_attachments', ['task_id'])
    op.create_index('ix_file_attachments_session_id', 'file_attachments', ['session_id'])
    op.create_index('ix_file_attachments_tenant_id', 'file_attachments', ['tenant_id'])
    op.create_index('ix_file_attachments_created_at', 'file_attachments', ['created_at'])


def downgrade() -> None:
    op.drop_table('file_attachments')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_sessions')
    op.drop_table('agent_memories')

    op.execute("DROP TYPE IF EXISTS session_status")
    op.execute("DROP TYPE IF EXISTS memory_type")
    op.execute("DROP EXTENSION IF EXISTS vector")
