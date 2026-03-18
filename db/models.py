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
    narration_en = Column(Text, nullable=True)
    title = Column(String)
    tags = Column(JSON)
    lang = Column(String, default="es")       # es/en/both
    # YouTube
    yt_video_id = Column(String, nullable=True)
    yt_url = Column(String, nullable=True)
    yt_url_en = Column(String, nullable=True)
    yt_backup_url = Column(String, nullable=True)
    # Instagram
    ig_url = Column(String, nullable=True)
    ig_url_en = Column(String, nullable=True)
    # TikTok
    tiktok_url = Column(String, nullable=True)
    tiktok_url_en = Column(String, nullable=True)
    # Metadata
    description = Column(Text, nullable=True)
    title_en = Column(String, nullable=True)
    description_en = Column(Text, nullable=True)
    tags_en = Column(JSON, nullable=True)
    category = Column(String, default="finanzas")
    status = Column(String, default="pending")   # pending/generating/generated/success/failed
    error = Column(Text, nullable=True)
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    generation_time_s = Column(Integer, nullable=True)  # Segundos que tardó en generarse


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


def get_oldest_generated() -> dict | None:
    """Devuelve el vídeo más antiguo con status='generated' listo para publicar."""
    with Session() as s:
        v = s.query(PublishedVideo)\
             .filter_by(status="generated")\
             .order_by(PublishedVideo.created_at.asc())\
             .first()
        if not v:
            return None
        return {
            "job_id": v.job_id, "topic": v.topic, "hook": v.hook,
            "narration": v.narration, "narration_en": v.narration_en,
            "title": v.title, "tags": v.tags,
            "title_en": v.title_en, "description_en": v.description_en,
            "tags_en": v.tags_en,
            "description": v.description, "category": v.category,
        }


def update_metadata(job_id: str, **kwargs):
    """Actualiza campos de metadata en un vídeo existente."""
    with Session() as s:
        v = s.query(PublishedVideo).filter_by(job_id=job_id).first()
        if v:
            for key, val in kwargs.items():
                if hasattr(v, key) and val is not None:
                    setattr(v, key, val)
            s.commit()


def mark_topic_used(topic_id: int, job_id: str):
    with Session() as s:
        t = s.query(TopicIdea).filter_by(id=topic_id).first()
        if t:
            t.estado = "usado"
            t.job_id = job_id
            t.used_at = datetime.utcnow()
            s.commit()


def update_status(job_id: str, status: str, yt_id=None, yt_url=None,
                   ig_url=None, tiktok_url=None, description=None, error=None,
                   yt_backup_url=None, yt_url_en=None, ig_url_en=None,
                   tiktok_url_en=None, generation_time_s=None):
    with Session() as s:
        v = s.query(PublishedVideo).filter_by(job_id=job_id).first()
        if v:
            v.status = status
            v.yt_video_id = yt_id
            v.yt_url = yt_url
            if yt_backup_url:
                v.yt_backup_url = yt_backup_url
            if yt_url_en:
                v.yt_url_en = yt_url_en
            if ig_url:
                v.ig_url = ig_url
            if ig_url_en:
                v.ig_url_en = ig_url_en
            if tiktok_url:
                v.tiktok_url = tiktok_url
            if tiktok_url_en:
                v.tiktok_url_en = tiktok_url_en
            if description:
                v.description = description
            if generation_time_s:
                v.generation_time_s = generation_time_s
            v.error = error
            if status == "success":
                v.published_at = datetime.utcnow()
            v.lang = "both"
            s.commit()


# ═══════════════════════════════════════
# Funciones de búsqueda para la web
# ═══════════════════════════════════════

def search_videos(query: str = None, status: str = None,
                  category: str = None, limit: int = 50) -> list[dict]:
    """Busca vídeos por texto, status o categoría."""
    with Session() as s:
        q = s.query(PublishedVideo).order_by(PublishedVideo.created_at.desc())
        if status:
            q = q.filter(PublishedVideo.status == status)
        if category:
            q = q.filter(PublishedVideo.category == category)
        if query:
            pattern = f"%{query}%"
            q = q.filter(
                (PublishedVideo.topic.ilike(pattern)) |
                (PublishedVideo.hook.ilike(pattern)) |
                (PublishedVideo.narration.ilike(pattern)) |
                (PublishedVideo.title.ilike(pattern))
            )
        rows = q.limit(limit).all()
        return [
            {
                "id": r.id, "job_id": r.job_id, "topic": r.topic,
                "hook": r.hook, "title": r.title, "status": r.status,
                "lang": r.lang, "category": r.category,
                "yt_url": r.yt_url, "yt_url_en": r.yt_url_en,
                "ig_url": r.ig_url, "tiktok_url": r.tiktok_url,
                "created_at": str(r.created_at) if r.created_at else None,
                "published_at": str(r.published_at) if r.published_at else None,
                "generation_time_s": r.generation_time_s,
            }
            for r in rows
        ]


def get_stats() -> dict:
    """Estadísticas para el dashboard."""
    with Session() as s:
        total = s.query(PublishedVideo).count()
        success = s.query(PublishedVideo).filter_by(status="success").count()
        failed = s.query(PublishedVideo).filter_by(status="failed").count()
        pending_topics = s.query(TopicIdea).filter_by(estado="pendiente").count()
        return {
            "total_videos": total,
            "success": success,
            "failed": failed,
            "pending_topics": pending_topics,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        }
