from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class PublishedVideo(Base):
    __tablename__ = "published_videos"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, nullable=False)
    topic = Column(String, nullable=False)
    hook = Column(String)
    narration = Column(Text)
    title = Column(String)
    tags = Column(JSON)
    yt_video_id = Column(String, nullable=True)
    yt_url = Column(String, nullable=True)
    status = Column(String, default="pending")   # pending/success/failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


DB_PATH = os.environ.get("DB_PATH", "db/videobot.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)


def init_db():
    os.makedirs("db", exist_ok=True)
    Base.metadata.create_all(engine)


def get_recent_topics(limit: int = 20) -> list[str]:
    with Session() as s:
        rows = s.query(PublishedVideo.topic)\
                .order_by(PublishedVideo.created_at.desc())\
                .limit(limit).all()
        return [r.topic for r in rows]


def save_video(job_id, topic, hook, narration, title, tags) -> PublishedVideo:
    with Session() as s:
        v = PublishedVideo(
            job_id=job_id, topic=topic, hook=hook,
            narration=narration, title=title, tags=tags
        )
        s.add(v)
        s.commit()
        return v


def update_status(job_id: str, status: str, yt_id=None, yt_url=None, error=None):
    with Session() as s:
        v = s.query(PublishedVideo).filter_by(job_id=job_id).first()
        if v:
            v.status = status
            v.yt_video_id = yt_id
            v.yt_url = yt_url
            v.error = error
            if status == "success":
                v.published_at = datetime.utcnow()
            s.commit()
