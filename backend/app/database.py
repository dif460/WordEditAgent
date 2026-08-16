"""数据库访问层（SQLAlchemy + PostgreSQL）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    file_id = Column(String(36), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending/running/success/failed
    progress = Column(Float, nullable=False, default=0.0)
    requirements = Column(Text, nullable=False, default="")
    format_rules = Column(Text, nullable=True)  # JSON
    output_path = Column(String(512), nullable=True)
    preview_pdf = Column(String(512), nullable=True)
    preview_png = Column(String(512), nullable=True)
    report = Column(Text, nullable=True)  # JSON
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    estimated_seconds = Column(Integer, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "status": self.status,
            "progress": self.progress,
            "requirements": self.requirements,
            "format_rules": json.loads(self.format_rules) if self.format_rules else None,
            "output_path": self.output_path,
            "preview_pdf": self.preview_pdf,
            "preview_png": self.preview_png,
            "report": json.loads(self.report) if self.report else None,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "estimated_seconds": self.estimated_seconds,
        }


engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """建表。"""
    Base.metadata.create_all(engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()