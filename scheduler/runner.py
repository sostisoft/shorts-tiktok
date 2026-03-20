"""
scheduler/runner.py
Orquestador principal del pipeline.
Conecta: ScriptAgent -> ImageGen -> VideoGen -> TTS -> MusicGen -> Composer -> DB -> Publisher

Funciones llamadas desde main.py:
- generate_only()         -> genera un video y lo guarda en output/pending/
- publish_only()          -> publica el siguiente video pendiente en YouTube
- night_generation_loop() -> genera videos en bucle entre 00:00 y 06:00
- run_job()               -> genera + publica inmediatamente (test)
- resume_job()            -> reanuda un job fallido/interrumpido
"""
import json as json_lib
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
from publishers.youtube_publisher import YouTubePublisher
from scheduler.checkpoint import JobCheckpoint, JOBS_DIR

logger = logging.getLogger("videobot.runner")

# Motor de vídeo: "kenburns" (rápido, FFmpeg) o "wan21" (IA, GPU, lento)
VIDEO_ENGINE = os.getenv("VIDEO_ENGINE", "kenburns")


def _get_video_generator():
    """Devuelve el generador de vídeo según la configuración."""
    if VIDEO_ENGINE == "wan21":
        from pipeline.video_gen import VideoGenerator
        logger.info(f"Motor de vídeo: Wan2.1 I2V (GPU, lento, IA)")
        return VideoGenerator()
    else:
        from pipeline.kenburns import KenBurnsGenerator
        logger.info(f"Motor de vídeo: Ken Burns (FFmpeg, rápido, sin GPU)")
        return KenBurnsGenerator()

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
PENDING_DIR = OUTPUT_DIR / "pending"
PUBLISHED_DIR = OUTPUT_DIR / "published"

# Ventana de generacion nocturna
NIGHT_START = dtime(0, 0)
NIGHT_END = dtime(6, 0)

# Maximo de videos por ciclo nocturno (para no saturar la cuota YouTube)
MAX_VIDEOS_PER_NIGHT = int(os.getenv("MAX_VIDEOS_PER_NIGHT", "6"))


# == API publica (llamada desde main.py) ======================================

def generate_only(topic: str | None = None, script: dict | None = None) -> str | None:
    """Genera un video y lo registra en DB como pendiente. Devuelve el job_id."""
    try:
        job_id = _run_generation_pipeline(topic=topic, script_override=script)
        return job_id
    except Exception as e:
        logger.error(f"generate_only fallo: {e}", exc_info=True)
        return None


def resume_job(job_id: str | None = None) -> str | None:
    """
    Reanuda un job fallido o interrumpido.
    Si job_id es None, busca el mas reciente incompleto.
    """
    try:
        if job_id:
            checkpoint = JobCheckpoint.load(job_id)
            if checkpoint.data["status"] == "done":
                logger.info(f"Job {job_id} ya esta completado, nada que resumir")
                return None
        else:
            checkpoint = JobCheckpoint.load_latest_incomplete()
            if checkpoint is None:
                logger.info("No hay jobs incompletos para resumir")
                return None

        logger.info(f"Resumiendo job {checkpoint.job_id} desde fase {checkpoint.next_phase()}")
        result = _run_generation_pipeline(resume_checkpoint=checkpoint)
        return result
    except FileNotFoundError:
        logger.error(f"No se encontro checkpoint para job {job_id}")
        return None
    except Exception as e:
        logger.error(f"resume_job fallo: {e}", exc_info=True)
        return None


def publish_only() -> str | None:
    """Publica el siguiente video pendiente en YouTube. Devuelve el job_id publicado."""
    try:
        return _publish_next_pending()
    except Exception as e:
        logger.error(f"publish_only fallo: {e}", exc_info=True)
        return None


def night_generation_loop():
    """Genera videos en bucle mientras estemos dentro de la ventana nocturna."""
    logger.info("Iniciando bucle de generacion nocturna...")

    # Primero intentar resumir jobs incompletos
    incomplete = JobCheckpoint.load_latest_incomplete()
    if incomplete:
        logger.info(f"Resumiendo job incompleto {incomplete.job_id} antes de generar nuevos")
        resume_job(incomplete.job_id)

    count = 0
    while _in_night_window() and count < MAX_VIDEOS_PER_NIGHT:
        logger.info(f"Video nocturno {count + 1}/{MAX_VIDEOS_PER_NIGHT}")
        job_id = generate_only()
        if job_id:
            count += 1
            logger.info(f"Video {count} generado: {job_id}")
        else:
            logger.error("Generacion fallo, esperando 5 min antes de reintentar...")
            time.sleep(300)

    logger.info(f"Bucle nocturno terminado: {count} videos generados")


def run_job():
    """Genera + publica inmediatamente (modo test / ejecucion manual)."""
    job_id = generate_only()
    if job_id:
        publish_only()
    else:
        logger.error("run_job: la generacion fallo, no se puede publicar")


def list_jobs_status() -> list[dict]:
    """Lista todos los jobs con su estado de checkpoint."""
    return JobCheckpoint.list_all()


# == Pipeline de generacion ====================================================

def _run_generation_pipeline(
    topic: str | None = None,
    resume_checkpoint: JobCheckpoint | None = None,
    script_override: dict | None = None,
) -> str:
    """
    Pipeline completo: guion -> imagenes -> video IA -> TTS -> musica -> compositing -> DB.
    Si resume_checkpoint se proporciona, reanuda desde la ultima fase completada.
    Devuelve el job_id del video generado.
    """
    # -- Decidir si es nuevo o resume --
    if resume_checkpoint is not None:
        checkpoint = resume_checkpoint
        job_id = checkpoint.job_id
        checkpoint.data["status"] = "running"
        checkpoint.data["updated_at"] = datetime.utcnow().isoformat()
        checkpoint.save()
        logger.info(f"=== Resumiendo pipeline [{job_id}] desde fase {checkpoint.next_phase()} ===")
    else:
        # Comprobar si hay un job incompleto reciente antes de crear uno nuevo
        checkpoint = JobCheckpoint.load_latest_incomplete()
        if checkpoint is not None:
            job_id = checkpoint.job_id
            checkpoint.data["status"] = "running"
            checkpoint.data["updated_at"] = datetime.utcnow().isoformat()
            checkpoint.save()
            logger.info(f"=== Resumiendo job incompleto [{job_id}] desde fase {checkpoint.next_phase()} ===")
        else:
            job_id = str(uuid.uuid4())[:8]
            checkpoint = None  # Se creara despues de la fase 1
            logger.info(f"=== Iniciando pipeline [{job_id}] ===")

    work_dir = JOBS_DIR / (checkpoint.job_id if checkpoint else job_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    t_total = time.time()

    # == 1. Guion ==============================================================
    if checkpoint and checkpoint.is_phase_done(1):
        logger.info("[1/6] Ya completada -- cargando guion desde checkpoint")
        script = checkpoint.data["script"]
    elif script_override:
        logger.info("[1/6] Usando guion manual (pasado por web)")
        script = script_override
        t1 = time.time()
        if checkpoint is None:
            checkpoint = JobCheckpoint.create(job_id, script.get("title", ""), script)
            work_dir = checkpoint.job_dir
        else:
            checkpoint.data["script"] = script
        script_path = work_dir / "phase_01_script.json"
        with open(script_path, "w") as f:
            json_lib.dump(script, f, ensure_ascii=False, indent=2)
        checkpoint.complete_phase(1, "phase_01_script.json", time.time() - t1)
    else:
        logger.info("[1/6] Generando guion...")
        if checkpoint:
            checkpoint.start_phase(1)
        t1 = time.time()
        try:
            agent = ScriptAgent()
            script = agent.generate(topic=topic)
            duration_1 = time.time() - t1

            # Crear checkpoint si es un job nuevo
            if checkpoint is None:
                checkpoint = JobCheckpoint.create(job_id, script.get("title", ""), script)
                work_dir = checkpoint.job_dir
            else:
                checkpoint.data["script"] = script

            # Guardar script como archivo
            script_path = work_dir / "phase_01_script.json"
            with open(script_path, "w") as f:
                json_lib.dump(script, f, ensure_ascii=False, indent=2)

            checkpoint.complete_phase(1, "phase_01_script.json", duration_1)
        except Exception as e:
            if checkpoint:
                checkpoint.fail_phase(1, str(e))
            raise

    title = script["title"]
    description = script.get("description", title)
    narration = script["narration"]
    scenes = script["scenes"]
    tags = script.get("tags", [])

    logger.info(f"  Titulo: {title}")
    logger.info(f"  Escenas: {len(scenes)}")

    # == 2. Imagenes (FLUX Schnell) ============================================
    if checkpoint.is_phase_done(2):
        logger.info("[2/6] Ya completada -- cargando imagenes desde checkpoint")
        images_dir = work_dir / checkpoint.get_phase_output(2)
        image_paths = sorted(images_dir.glob("*.png"))
        if not image_paths:
            image_paths = sorted(images_dir.glob("*.jpg"))
    else:
        logger.info("[2/6] Generando imagenes de fondo con FLUX Schnell...")
        checkpoint.start_phase(2)
        t2 = time.time()
        try:
            image_gen = ImageGenerator(model="schnell")
            image_prompts = [s["image_prompt"] for s in scenes]
            image_paths = image_gen.generate_batch(
                prompts=image_prompts,
                output_dir=work_dir / "images",
                width=576,
                height=1024,
                steps=4,
            )
            duration_2 = time.time() - t2
            checkpoint.complete_phase(2, "images", duration_2)
            logger.info(f"  {len(image_paths)} imagenes generadas")
        except Exception as e:
            checkpoint.fail_phase(2, str(e))
            raise

    # == 3. TTS ================================================================
    if checkpoint.is_phase_done(3):
        logger.info("[3/6] Ya completada -- cargando voz desde checkpoint")
        voice_path = work_dir / checkpoint.get_phase_output(3)
    else:
        logger.info("[3/6] Generando voz TTS (CPU)...")
        checkpoint.start_phase(3)
        t3 = time.time()
        try:
            tts = TTSGenerator()
            voice_path = tts.generate(
                text=narration,
                output_path=work_dir / "voice.wav",
            )
            duration_3 = time.time() - t3
            checkpoint.complete_phase(3, "voice.wav", duration_3)
        except Exception as e:
            checkpoint.fail_phase(3, str(e))
            raise

    tts_for_duration = TTSGenerator()
    voice_duration = tts_for_duration.get_duration(voice_path)
    logger.info(f"  Voz: {voice_duration:.1f}s")

    # == 4. Video IA (Wan2.1 I2V) ==============================================
    if checkpoint.is_phase_done(4):
        logger.info("[4/6] Ya completada -- cargando clips desde checkpoint")
        clip_dir = work_dir / checkpoint.get_phase_output(4)
        clip_paths = sorted(clip_dir.glob("*.mp4"))
    else:
        logger.info(f"[4/6] Generando clips de video ({VIDEO_ENGINE})...")
        checkpoint.start_phase(4)
        t4 = time.time()
        try:
            video_gen = _get_video_generator()
            motion_prompts = _build_motion_prompts(scenes)
            clip_dir = work_dir / "clips"
            clip_dir.mkdir(parents=True, exist_ok=True)
            clip_paths = []
            for i, (img_path, prompt) in enumerate(zip(image_paths, motion_prompts)):
                clip_path = clip_dir / f"clip_{i:02d}.mp4"
                logger.info(f"  Clip {i+1}/{len(image_paths)}...")
                video_gen.animate(img_path, prompt, clip_path, duration_seconds=5)
                clip_paths.append(clip_path)
            video_gen.unload()
            duration_4 = time.time() - t4
            checkpoint.complete_phase(4, "clips", duration_4)
            logger.info(f"  {len(clip_paths)} clips de video generados")
        except Exception as e:
            checkpoint.fail_phase(4, str(e))
            raise

    # == 5. Musica de fondo ====================================================
    if checkpoint.is_phase_done(5):
        logger.info("[5/6] Ya completada -- cargando musica desde checkpoint")
        music_path = work_dir / checkpoint.get_phase_output(5)
    else:
        logger.info("[5/6] Generando musica de fondo con MusicGen...")
        checkpoint.start_phase(5)
        t5 = time.time()
        try:
            music_gen = MusicGenerator()
            music_path = music_gen.generate(
                duration_seconds=voice_duration + 3,
                output_path=work_dir / "music.wav",
            )
            duration_5 = time.time() - t5
            checkpoint.complete_phase(5, "music.wav", duration_5)
        except Exception as e:
            checkpoint.fail_phase(5, str(e))
            raise

    # == 6. Compositing final ==================================================
    if checkpoint.is_phase_done(6):
        logger.info("[6/6] Ya completada -- video final ya existe")
        final_path = PENDING_DIR / f"{job_id}.mp4"
    else:
        logger.info("[6/6] Compositing final con FFmpeg...")
        checkpoint.start_phase(6)
        t6 = time.time()
        try:
            composer = VideoComposer()
            # Subtítulos de la NARRACIÓN (lo que se dice por voz), no los títulos de escena
            subtitle_segments = VideoComposer.build_subtitle_segments_from_narration(
                narration_text=narration,
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
            duration_6 = time.time() - t6
            checkpoint.complete_phase(6, str(final_path), duration_6)
        except Exception as e:
            checkpoint.fail_phase(6, str(e))
            raise

    # == 7. Registrar en DB ====================================================
    _save_to_db(
        job_id=job_id,
        title=title,
        description=description,
        tags=tags,
        video_path=final_path,
        script=script,
    )

    elapsed = time.time() - t_total
    logger.info(f"=== Pipeline [{job_id}] completado en {elapsed/60:.1f} min ===")
    logger.info(f"  -> {final_path}")

    # Marcar checkpoint como done y limpiar directorio del job
    checkpoint.data["status"] = "done"
    checkpoint.data["updated_at"] = datetime.utcnow().isoformat()
    checkpoint.save()

    # Limpiar directorio del job (ya no se necesita, el video esta en pending/)
    shutil.rmtree(checkpoint.job_dir, ignore_errors=True)

    return job_id


# == Pipeline de publicacion ===================================================

def _publish_next_pending() -> str | None:
    """Publica el siguiente video de la cola pending en YouTube."""
    with Session() as session:
        video = (
            session.query(Video)
            .filter(Video.status == VideoStatus.PENDING)
            .order_by(Video.created_at)
            .first()
        )
        if video is None:
            logger.info("No hay videos pendientes para publicar")
            return None

        video_path = Path(video.video_path)
        if not video_path.exists():
            logger.error(f"Video no encontrado en disco: {video_path}")
            video.status = VideoStatus.ERROR
            video.error_message = "Fichero no encontrado en disco"
            session.commit()
            return None

        logger.info(f"Publicando video: {video.job_id} -- {video.title}")
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
            return None


# == Utilidades internas =======================================================

def _build_motion_prompts(scenes: list[dict]) -> list[str]:
    """
    Genera prompts de movimiento para Wan2GP I2V.
    Wan2.1 I2V funciona mejor con prompts descriptivos del movimiento de camara.
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
    """Registra el video generado en SQLite."""
    with Session() as session:
        # Comprobar si ya existe (en caso de resume)
        existing = session.query(Video).filter(Video.job_id == job_id).first()
        if existing:
            logger.info(f"Video {job_id} ya existe en DB, actualizando")
            existing.video_path = str(video_path)
            existing.status = VideoStatus.PENDING
            existing.error_message = None
            session.commit()
            return

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
        logger.info(f"Video registrado en DB: {job_id}")


def _in_night_window() -> bool:
    now = datetime.now().time()
    return NIGHT_START <= now < NIGHT_END
