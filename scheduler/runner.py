"""
scheduler/runner.py
Orquestador principal del pipeline.
Conecta: ScriptAgent → ImageGen → VideoGen → TTS → MusicGen → Composer → DB → Publisher

Funciones llamadas desde main.py:
- generate_only()         → genera un vídeo y lo guarda en output/pending/
- publish_only()          → publica el siguiente vídeo pendiente en YouTube
- night_generation_loop() → genera vídeos en bucle entre 00:00 y 06:00
- run_job()               → genera + publica inmediatamente (test)
"""
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, time as dtime
from pathlib import Path

from agents.script_agent import ScriptAgent
from db.models import Session, Video, VideoStatus
from pipeline.composer import VideoComposer
from pipeline.image_gen import ImageGenerator
from pipeline.music_gen import MusicGenerator
from pipeline.tts import TTSGenerator
from pipeline.video_generator import VideoGenerator
from publishers.youtube_publisher import YouTubePublisher

logger = logging.getLogger("videobot.runner")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
PENDING_DIR = OUTPUT_DIR / "pending"
PUBLISHED_DIR = OUTPUT_DIR / "published"

# Ventana de generación nocturna
NIGHT_START = dtime(0, 0)
NIGHT_END = dtime(6, 0)

# Máximo de vídeos por ciclo nocturno (para no saturar la cuota YouTube)
MAX_VIDEOS_PER_NIGHT = int(os.getenv("MAX_VIDEOS_PER_NIGHT", "6"))


# ── API pública (llamada desde main.py) ───────────────────────────────────────

def generate_only() -> str | None:
    """Genera un vídeo y lo registra en DB como pendiente. Devuelve el job_id."""
    try:
        job_id = _run_generation_pipeline()
        return job_id
    except Exception as e:
        logger.error(f"generate_only falló: {e}", exc_info=True)
        return None


def publish_only() -> str | None:
    """Publica el siguiente vídeo pendiente en YouTube. Devuelve el job_id publicado."""
    try:
        return _publish_next_pending()
    except Exception as e:
        logger.error(f"publish_only falló: {e}", exc_info=True)
        return None


def night_generation_loop():
    """Genera vídeos en bucle mientras estemos dentro de la ventana nocturna."""
    logger.info("Iniciando bucle de generación nocturna...")
    count = 0
    while _in_night_window() and count < MAX_VIDEOS_PER_NIGHT:
        logger.info(f"Vídeo nocturno {count + 1}/{MAX_VIDEOS_PER_NIGHT}")
        job_id = generate_only()
        if job_id:
            count += 1
            logger.info(f"Vídeo {count} generado: {job_id}")
        else:
            logger.error("Generación falló, esperando 5 min antes de reintentar...")
            time.sleep(300)

    logger.info(f"Bucle nocturno terminado: {count} vídeos generados")


def run_job():
    """Genera + publica inmediatamente (modo test / ejecución manual)."""
    job_id = generate_only()
    if job_id:
        publish_only()
    else:
        logger.error("run_job: la generación falló, no se puede publicar")


# ── Pipeline de generación ────────────────────────────────────────────────────

def _run_generation_pipeline(topic: str | None = None) -> str:
    """
    Pipeline completo: guión → imágenes → video IA → TTS → música → compositing → DB.
    Devuelve el job_id del vídeo generado.
    """
    job_id = str(uuid.uuid4())[:8]
    work_dir = OUTPUT_DIR / "tmp" / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    t_total = time.time()

    logger.info(f"═══ Iniciando pipeline [{job_id}] ═══")

    # ── 1. Guión ─────────────────────────────────────────────────────────────
    logger.info("[1/6] Generando guión...")
    agent = ScriptAgent()
    script = agent.generate(topic=topic)
    title = script["title"]
    description = script.get("description", title)
    narration = script["narration"]
    scenes = script["scenes"]           # lista de {text, image_prompt}
    tags = script.get("tags", [])

    logger.info(f"  Título: {title}")
    logger.info(f"  Escenas: {len(scenes)}")

    # ── 2. Imágenes (FLUX Schnell) — batch para una sola carga del modelo ────
    logger.info("[2/6] Generando imágenes de fondo con FLUX Schnell...")
    image_gen = ImageGenerator(model="schnell")
    image_prompts = [s["image_prompt"] for s in scenes]
    image_paths = image_gen.generate_batch(
        prompts=image_prompts,
        output_dir=work_dir / "images",
        width=576,      # ancho base: se escala a 1080 en FFmpeg
        height=1024,    # alto base: se escala a 1920 en FFmpeg
        steps=4,
    )
    logger.info(f"  {len(image_paths)} imágenes generadas")

    # ── 3. TTS en paralelo con el inicio de la generación de video ────────────
    # (TTS es CPU, no compite con GPU)
    logger.info("[3/6] Generando voz TTS (CPU)...")
    tts = TTSGenerator()
    voice_path = tts.generate(
        text=narration,
        output_path=work_dir / "voice.wav",
    )
    voice_duration = tts.get_duration(voice_path)
    logger.info(f"  Voz generada: {voice_duration:.1f}s")

    # ── 4. Video IA (Wan2GP I2V + Self-Forcing LoRA) ─────────────────────────
    logger.info("[4/6] Animando imágenes con Wan2GP I2V (Self-Forcing 2 steps)...")
    video_gen = VideoGenerator(
        model="wan_i2v_1.3B",
        lora="self_forcing",
        steps=2,
        fps=16,
        width=480,
        height=832,
        duration_seconds=5.0,
    )
    # Prompts de movimiento para cada escena
    motion_prompts = _build_motion_prompts(scenes)
    clip_paths = video_gen.animate_batch(
        images=image_paths,
        prompts=motion_prompts,
        output_dir=work_dir / "clips",
    )
    logger.info(f"  {len(clip_paths)} clips de video generados")

    # ── 5. Música de fondo ───────────────────────────────────────────────────
    logger.info("[5/6] Generando música de fondo con MusicGen...")
    music_gen = MusicGenerator()
    music_path = music_gen.generate(
        duration_seconds=voice_duration + 3,
        output_path=work_dir / "music.wav",
    )

    # ── 6. Compositing final ─────────────────────────────────────────────────
    logger.info("[6/6] Compositing final con FFmpeg...")
    composer = VideoComposer()
    subtitle_segments = VideoComposer.build_subtitle_segments_from_script(
        script_lines=[s["text"] for s in scenes],
        total_duration=voice_duration,
    )

    final_path = PENDING_DIR / f"{job_id}.mp4"
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    composer.compose(
        clips=clip_paths,
        audio_voice=voice_path,
        audio_music=music_path,
        subtitles=subtitle_segments,
        output_path=final_path,
        target_duration=voice_duration + 1,
    )

    # ── 7. Registrar en DB ───────────────────────────────────────────────────
    _save_to_db(
        job_id=job_id,
        title=title,
        description=description,
        tags=tags,
        video_path=final_path,
        script=script,
    )

    elapsed = time.time() - t_total
    logger.info(f"═══ Pipeline [{job_id}] completado en {elapsed/60:.1f} min ═══")
    logger.info(f"  → {final_path}")

    # Limpiar directorio temporal
    shutil.rmtree(work_dir, ignore_errors=True)

    return job_id


# ── Pipeline de publicación ───────────────────────────────────────────────────

def _publish_next_pending() -> str | None:
    """Publica el siguiente vídeo de la cola pending en YouTube."""
    with Session() as session:
        video = (
            session.query(Video)
            .filter(Video.status == VideoStatus.PENDING)
            .order_by(Video.created_at)
            .first()
        )
        if video is None:
            logger.info("No hay vídeos pendientes para publicar")
            return None

        video_path = Path(video.video_path)
        if not video_path.exists():
            logger.error(f"Vídeo no encontrado en disco: {video_path}")
            video.status = VideoStatus.ERROR
            video.error_message = "Fichero no encontrado en disco"
            session.commit()
            return None

        logger.info(f"Publicando vídeo: {video.job_id} — {video.title}")
        publisher = YouTubePublisher()
        try:
            yt_id = publisher.upload(
                video_path=video_path,
                title=video.title,
                description=video.description,
                tags=video.tags.split(",") if video.tags else [],
            )
            video.status = VideoStatus.PUBLISHED
            video.youtube_id = yt_id
            video.published_at = datetime.utcnow()
            session.commit()

            # Mover a carpeta published
            dest = PUBLISHED_DIR / video_path.name
            PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(video_path), str(dest))
            video.video_path = str(dest)
            session.commit()

            logger.info(f"Publicado en YouTube: https://youtube.com/watch?v={yt_id}")
            return video.job_id

        except Exception as e:
            logger.error(f"Error al publicar {video.job_id}: {e}")
            video.status = VideoStatus.ERROR
            video.error_message = str(e)[:500]
            session.commit()
            # No mover el fichero — quedará en pending para reintentar
            return None


# ── Utilidades internas ───────────────────────────────────────────────────────

def _build_motion_prompts(scenes: list[dict]) -> list[str]:
    """
    Genera prompts de movimiento para Wan2GP I2V.
    Wan2.1 I2V funciona mejor con prompts descriptivos del movimiento de cámara.
    """
    motion_templates = [
        "slow camera zoom in, smooth motion, cinematic, professional",
        "gentle camera pan left, particles floating, atmospheric light",
        "slow dolly forward, depth of field blur, cinematic movement",
        "subtle camera shake, dynamic, energetic, professional video",
        "slow zoom out revealing scene, smooth cinematic movement",
    ]
    prompts = []
    for i, scene in enumerate(scenes):
        # Combinar el contexto de la escena con el movimiento de cámara
        base_motion = motion_templates[i % len(motion_templates)]
        scene_context = scene.get("image_prompt", "")[:100]
        prompts.append(f"{scene_context}, {base_motion}")
    return prompts


def _save_to_db(
    job_id: str,
    title: str,
    description: str,
    tags: list[str],
    video_path: Path,
    script: dict,
):
    """Registra el vídeo generado en SQLite."""
    import json as json_lib
    with Session() as session:
        video = Video(
            job_id=job_id,
            title=title,
            description=description,
            tags=",".join(tags),
            video_path=str(video_path),
            script_json=json_lib.dumps(script, ensure_ascii=False),
            status=VideoStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        session.add(video)
        session.commit()
        logger.info(f"Vídeo registrado en DB: {job_id}")


def _in_night_window() -> bool:
    now = datetime.now().time()
    return NIGHT_START <= now < NIGHT_END
