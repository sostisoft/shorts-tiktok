"""
db/models.py
Modelos SQLAlchemy para SQLite.
Registra cada vídeo generado y su estado de publicación.
"""
import enum
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import (Column, DateTime, Enum, String, Text, create_engine)
from sqlalchemy.orm import DeclarativeBase, Session as SASession, sessionmaker

DB_PATH = Path(os.getenv("DB_PATH", "db/videobot.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
_SessionFactory = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    ERROR = "error"
    SKIPPED = "skipped"


class Video(Base):
    __tablename__ = "videos"

    job_id = Column(String(16), primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, default="")
    tags = Column(String(500), default="")
    video_path = Column(String(500), nullable=False)
    youtube_id = Column(String(20), nullable=True)
    script_json = Column(Text, default="{}")
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Video {self.job_id} [{self.status}] '{self.title[:40]}'>"


def init_db():
    """Crea las tablas si no existen."""
    Base.metadata.create_all(engine)


# Context manager para sesiones
class Session:
    """
    Uso:
        with Session() as session:
            session.add(video)
            session.commit()
    """
    def __enter__(self) -> SASession:
        self._session = _SessionFactory()
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._session.rollback()
        self._session.close()
        return False
