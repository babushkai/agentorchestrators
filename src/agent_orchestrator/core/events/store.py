"""Event store for event sourcing."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import Column, DateTime, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from agent_orchestrator.core.events.models import DomainEvent
from agent_orchestrator.infrastructure.persistence.database import Base

logger = structlog.get_logger(__name__)


class EventRecord(Base):
    """SQLAlchemy model for stored events."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(PGUUID(as_uuid=True), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    aggregate_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    correlation_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    causation_id = Column(PGUUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, nullable=False, default={})
    metadata = Column(JSONB, nullable=False, default={})


class EventStore(ABC):
    """Abstract event store interface."""

    @abstractmethod
    async def append(self, event: DomainEvent) -> None:
        """Append an event to the store."""
        ...

    @abstractmethod
    async def append_batch(self, events: list[DomainEvent]) -> None:
        """Append multiple events atomically."""
        ...

    @abstractmethod
    async def get_events(
        self,
        aggregate_id: UUID,
        after_version: int = 0,
    ) -> list[DomainEvent]:
        """Get events for an aggregate after a given version."""
        ...

    @abstractmethod
    async def get_events_by_type(
        self,
        event_type: str,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[DomainEvent]:
        """Get events by type, optionally after a timestamp."""
        ...

    @abstractmethod
    async def get_events_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[DomainEvent]:
        """Get all events in a correlation chain."""
        ...


class PostgresEventStore(EventStore):
    """PostgreSQL-backed event store."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def append(self, event: DomainEvent) -> None:
        async with self._session_factory() as session:
            record = EventRecord(
                event_id=event.event_id,
                event_type=event.event_type.value,
                aggregate_id=event.aggregate_id,
                aggregate_type=event.aggregate_type,
                tenant_id=event.tenant_id,
                version=event.version,
                timestamp=event.timestamp,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                payload=event.payload,
                metadata=event.metadata,
            )
            session.add(record)
            await session.commit()

        logger.debug(
            "Event appended",
            event_id=str(event.event_id),
            event_type=event.event_type.value,
            aggregate_id=str(event.aggregate_id),
        )

    async def append_batch(self, events: list[DomainEvent]) -> None:
        if not events:
            return

        async with self._session_factory() as session:
            records = [
                EventRecord(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    aggregate_id=event.aggregate_id,
                    aggregate_type=event.aggregate_type,
                    tenant_id=event.tenant_id,
                    version=event.version,
                    timestamp=event.timestamp,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    payload=event.payload,
                    metadata=event.metadata,
                )
                for event in events
            ]
            session.add_all(records)
            await session.commit()

        logger.debug("Events appended", count=len(events))

    async def get_events(
        self,
        aggregate_id: UUID,
        after_version: int = 0,
    ) -> list[DomainEvent]:
        async with self._session_factory() as session:
            stmt = (
                select(EventRecord)
                .where(EventRecord.aggregate_id == aggregate_id)
                .where(EventRecord.version > after_version)
                .order_by(EventRecord.version)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

        return [self._record_to_event(r) for r in records]

    async def get_events_by_type(
        self,
        event_type: str,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[DomainEvent]:
        async with self._session_factory() as session:
            stmt = select(EventRecord).where(EventRecord.event_type == event_type)

            if after:
                stmt = stmt.where(EventRecord.timestamp > after)

            stmt = stmt.order_by(EventRecord.timestamp).limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()

        return [self._record_to_event(r) for r in records]

    async def get_events_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[DomainEvent]:
        async with self._session_factory() as session:
            stmt = (
                select(EventRecord)
                .where(EventRecord.correlation_id == correlation_id)
                .order_by(EventRecord.timestamp)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

        return [self._record_to_event(r) for r in records]

    def _record_to_event(self, record: EventRecord) -> DomainEvent:
        from agent_orchestrator.core.events.models import EventType

        return DomainEvent(
            event_id=record.event_id,
            event_type=EventType(record.event_type),
            aggregate_id=record.aggregate_id,
            aggregate_type=record.aggregate_type,
            tenant_id=record.tenant_id,
            version=record.version,
            timestamp=record.timestamp,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            payload=record.payload,
            metadata=record.metadata,
        )


class InMemoryEventStore(EventStore):
    """In-memory event store for testing."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    async def append(self, event: DomainEvent) -> None:
        self._events.append(event)

    async def append_batch(self, events: list[DomainEvent]) -> None:
        self._events.extend(events)

    async def get_events(
        self,
        aggregate_id: UUID,
        after_version: int = 0,
    ) -> list[DomainEvent]:
        return [
            e
            for e in self._events
            if e.aggregate_id == aggregate_id and e.version > after_version
        ]

    async def get_events_by_type(
        self,
        event_type: str,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[DomainEvent]:
        events = [e for e in self._events if e.event_type.value == event_type]
        if after:
            events = [e for e in events if e.timestamp > after]
        return events[:limit]

    async def get_events_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[DomainEvent]:
        return [e for e in self._events if e.correlation_id == correlation_id]
