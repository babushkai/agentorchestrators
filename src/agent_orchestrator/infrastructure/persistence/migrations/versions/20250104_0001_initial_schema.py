"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE agent_status AS ENUM ('idle', 'running', 'paused', 'error', 'terminated')")
    op.execute("CREATE TYPE task_status AS ENUM ('pending', 'queued', 'assigned', 'running', 'completed', 'failed', 'cancelled', 'timeout')")
    op.execute("CREATE TYPE workflow_status AS ENUM ('pending', 'running', 'paused', 'completed', 'failed', 'compensating', 'compensated', 'cancelled')")

    # Create agent_definitions table
    op.create_table(
        'agent_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(200), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('backstory', sa.Text(), nullable=True),
        sa.Column('model_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('tools', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('memory_config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('constraints', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('capabilities', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_agent_definitions')
    )
    op.create_index('ix_agent_definitions_tenant_id', 'agent_definitions', ['tenant_id'])

    # Create agent_instances table
    op.create_table(
        'agent_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('definition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('worker_id', sa.String(100), nullable=True),
        sa.Column('status', postgresql.ENUM('idle', 'running', 'paused', 'error', 'terminated', name='agent_status', create_type=False), nullable=False, server_default='idle'),
        sa.Column('current_task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tasks_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tasks_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_execution_time_ms', sa.Float(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['definition_id'], ['agent_definitions.id'], name='fk_agent_instances_definition_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_agent_instances')
    )
    op.create_index('ix_agent_instances_definition_id', 'agent_instances', ['definition_id'])
    op.create_index('ix_agent_instances_worker_id', 'agent_instances', ['worker_id'])

    # Create workflow_definitions table
    op.create_table(
        'workflow_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('version', sa.String(20), nullable=False, server_default='1.0.0'),
        sa.Column('steps', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('input_schema', postgresql.JSONB(), nullable=True),
        sa.Column('output_schema', postgresql.JSONB(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_workflow_definitions')
    )
    op.create_index('ix_workflow_definitions_tenant_id', 'workflow_definitions', ['tenant_id'])

    # Create workflow_executions table
    op.create_table(
        'workflow_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'paused', 'completed', 'failed', 'compensating', 'compensated', 'cancelled', name='workflow_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('current_step_id', sa.String(100), nullable=True),
        sa.Column('completed_steps', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('step_results', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('failed_step_id', sa.String(100), nullable=True),
        sa.Column('input_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),
        sa.Column('checkpoint_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_definitions.id'], name='fk_workflow_executions_workflow_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_workflow_executions')
    )
    op.create_index('ix_workflow_executions_workflow_id', 'workflow_executions', ['workflow_id'])
    op.create_index('ix_workflow_executions_tenant_id', 'workflow_executions', ['tenant_id'])
    op.create_index('ix_workflow_executions_status', 'workflow_executions', ['status'])

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('input_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('required_capabilities', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', postgresql.ENUM('pending', 'queued', 'assigned', 'running', 'completed', 'failed', 'cancelled', 'timeout', name='task_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('assigned_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('parent_workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('parent_step_id', sa.String(100), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['parent_workflow_id'], ['workflow_executions.id'], name='fk_tasks_parent_workflow_id', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_tasks')
    )
    op.create_index('ix_tasks_tenant_id', 'tasks', ['tenant_id'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_assigned_agent_id', 'tasks', ['assigned_agent_id'])
    op.create_index('ix_tasks_created_at', 'tasks', ['created_at'])

    # Create events table for event sourcing
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregate_type', sa.String(50), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('causation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('payload', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('id', name='pk_events')
    )
    op.create_index('ix_events_event_id', 'events', ['event_id'], unique=True)
    op.create_index('ix_events_event_type', 'events', ['event_type'])
    op.create_index('ix_events_aggregate_id', 'events', ['aggregate_id'])
    op.create_index('ix_events_aggregate_type', 'events', ['aggregate_type'])
    op.create_index('ix_events_tenant_id', 'events', ['tenant_id'])
    op.create_index('ix_events_timestamp', 'events', ['timestamp'])
    op.create_index('ix_events_correlation_id', 'events', ['correlation_id'])


def downgrade() -> None:
    op.drop_table('events')
    op.drop_table('tasks')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_definitions')
    op.drop_table('agent_instances')
    op.drop_table('agent_definitions')

    op.execute("DROP TYPE IF EXISTS workflow_status")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS agent_status")
