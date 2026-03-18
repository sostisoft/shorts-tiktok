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
    ig_url = Column(String, nullable=True)
    tiktok_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")   # pending/success/failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


class TopicIdea(Base):
    __tablename__ = "topic_ideas"

    id = Column(Integer, primary_key=True)
    tema = Column(String, nullable=False)
    enfoque = Column(String, nullable=True)
    titulo = Column(String, nullable=True)
    texto = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    categoria = Column(String, default="finanzas")  # finanzas/deporte/historia/etc
    prioridad = Column(String, default="normal")  # alta/normal/baja
    estado = Column(String, default="pendiente")   # pendiente/usado/descartado
    job_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)


DB_PATH = os.environ.get("DB_PATH", "db/videobot.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)


def init_db():
    os.makedirs("db", exist_ok=True)
    Base.metadata.create_all(engine)


def get_recent_topics(limit: int = 20) -> list[str]:
    """Solo devuelve temas con status 'success' — los failed se pueden reintentar."""
    with Session() as s:
        rows = s.query(PublishedVideo.topic)\
                .filter(PublishedVideo.status == "success")\
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


def get_pending_topics() -> list[dict]:
    """Devuelve temas pendientes ordenados por prioridad."""
    prio_order = {"alta": 0, "normal": 1, "baja": 2}
    with Session() as s:
        rows = s.query(TopicIdea).filter_by(estado="pendiente")\
                .order_by(TopicIdea.created_at.asc()).all()
        result = []
        for r in rows:
            result.append({
                "id": r.id, "tema": r.tema, "enfoque": r.enfoque,
                "prioridad": r.prioridad, "created_at": str(r.created_at),
            })
        result.sort(key=lambda x: prio_order.get(x["prioridad"], 1))
        return result


def mark_topic_used(topic_id: int, job_id: str):
    with Session() as s:
        t = s.query(TopicIdea).filter_by(id=topic_id).first()
        if t:
            t.estado = "usado"
            t.job_id = job_id
            t.used_at = datetime.utcnow()
            s.commit()


def update_status(job_id: str, status: str, yt_id=None, yt_url=None,
                   ig_url=None, tiktok_url=None, description=None, error=None):
    with Session() as s:
        v = s.query(PublishedVideo).filter_by(job_id=job_id).first()
        if v:
            v.status = status
            v.yt_video_id = yt_id
            v.yt_url = yt_url
            if ig_url:
                v.ig_url = ig_url
            if tiktok_url:
                v.tiktok_url = tiktok_url
            if description:
                v.description = description
            v.error = error
            if status == "success":
                v.published_at = datetime.utcnow()
            s.commit()
