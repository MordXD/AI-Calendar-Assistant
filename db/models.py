from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    TypeDecorator,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import ARRAY, Float


class Vector(TypeDecorator):
    """Custom type for pgvector.

    pgvector stores vectors as arrays of floats.
    """
    impl = ARRAY(Float)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return list(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return list(value)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Event(Base):
    """Local replica of calendar events."""
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="google")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Document(Base):
    """Text documents for search."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON string
    doc_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 'event', 'note', etc.
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Embedding(Base):
    """Vector embeddings."""
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)  # vector column
    model_version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="embeddings")


class Rule(Base):
    """User scheduling rules/constraints."""
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    rule_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 'time_slot', 'priority', etc.
    conditions: Mapped[dict] = mapped_column(Text, nullable=False)  # JSON string
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(None, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AuditLog(Base):
    """Audit log for actions."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 'create', 'update', 'delete'
    target_type: Mapped[str] = mapped_column(String, nullable=False)  # 'event', 'rule', etc.
    target_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)  # JSON string
    status: Mapped[str] = mapped_column(String, nullable=False, default="success")  # 'success', 'failed'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
