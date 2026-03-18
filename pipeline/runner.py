import json
import shutil
import logging
import threading
from pathlib import Path
from agents.orchestrator import VideoDecision
from pipeline.image_gen import ImageGenerator
from pipeline.image_bank import generate_with_cache, save_to_bank
from pipeline.video_gen import VideoGenerator
from pipeline.tts_engine import TTSEngine
from pipeline import editor

logger = logging.getLogger("videobot")

image_gen = ImageGenerator()
video_gen = VideoGenerator()
tts_engine = TTSEngine()

MUSIC_PATH = Path("assets/music/finance_background.mp3")

# GPU lock basado en fichero — funciona entre contenedores Docker
GPU_LOCK_FILE = Path("/app/output/.gpu_lock")


class FileLock:
    """Lock basado en fichero para coordinar GPU entre contenedores."""
    def __init__(self, path, timeout=3600):
        self.path = path
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        import fcntl, time
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = open(self.path, 'w')
        start = time.time()
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (IOError, OSError):
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"GPU lock timeout after {self.timeout}s")
                time.sleep(2)

    def __exit__(self, *args):
        import fcntl
        if self.fd:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()


gpu_lock = FileLock(GPU_LOCK_FILE)


def _load_checkpoint(tmp: Path) -> dict:
    cp_file = tmp / "checkpoint.json"
    if cp_file.exists():
        return json.loads(cp_file.read_text())
    return {"step": 0, "image_paths": [], "clip_paths": []}


def _save_checkpoint(tmp: Path, step: int, **kwargs):
    cp = {"step": step, **kwargs}
    for k, v in cp.items():
        if isinstance(v, list):
            cp[k] = [str(x) for x in v]
    (tmp / "checkpoint.json").write_text(json.dumps(cp))


def generate_video(decision: VideoDecision, job_id: str) -> Path:
    """
    Pipeline con checkpointing + GPU lock para paralelismo tipo swap.

    Fases GPU (con lock — 1 a la vez):
      - Paso 1: FLUX genera imágenes
      - Paso 2: Wan2.1 anima clips

    Fases CPU (sin lock — pueden correr en paralelo con otro job en GPU):
      - Paso 3: Concatenar clips (ffmpeg)
      - Paso 4: TTS (Kokoro)
      - Paso 5: Mix audio (ffmpeg)
      - Paso 6: Subtítulos (ffmpeg)
      - Paso 7: CTA overlay (ffmpeg)

    Resultado: mientras Job A hace pasos 3-7 en CPU, Job B puede hacer pasos 1-2 en GPU.
    """
    tmp = Path(f"output/tmp/{job_id}")
    tmp.mkdir(parents=True, exist_ok=True)

    cp = _load_checkpoint(tmp)
    start_step = cp.get("step", 0)
    if start_step > 0:
        logger.info(f"[{job_id}] Reanudando desde paso {start_step}")

    try:
        prompts = decision.image_prompts[:3]
        img_dir = tmp / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        # ════════════════════════════════════════
        # FASE GPU — con lock (1 a la vez)
        # ════════════════════════════════════════

        if start_step < 2:
            logger.info(f"[{job_id}] Esperando GPU lock...")
            with gpu_lock:
                logger.info(f"[{job_id}] GPU lock adquirido")

                # ── Paso 1: Generar imágenes con FLUX ──
                if start_step < 1:
                    logger.info(f"[{job_id}] Generando {len(prompts)} imagenes (con cache)...")
                    image_paths = generate_with_cache(
                        image_gen, prompts, job_id, img_dir,
                        topic=decision.topic, max_cached_per_video=1,
                    )
                    _save_checkpoint(tmp, 1, image_paths=image_paths, clip_paths=[])
                else:
                    image_paths = [Path(p) for p in cp.get("image_paths", [])]
                    logger.info(f"[{job_id}] Imagenes ya generadas, saltando")

                # ── Paso 2: Animar con Wan2.1 ──
                logger.info(f"[{job_id}] Animando imagenes con Wan2.1 (GPU)...")
                clip_paths = []
                for i, (img_path, prompt) in enumerate(zip(image_paths, prompts)):
                    clip_path = tmp / f"clip_{i:02d}.mp4"
                    if clip_path.exists() and clip_path.stat().st_size > 1000:
                        logger.info(f"[{job_id}]   Clip {i} ya existe, saltando")
                        clip_paths.append(clip_path)
                        continue
                    video_gen.animate(img_path, prompt, clip_path, duration_seconds=5)
                    clip_paths.append(clip_path)
                _save_checkpoint(tmp, 2, image_paths=image_paths, clip_paths=clip_paths)

            logger.info(f"[{job_id}] GPU lock liberado — otro job puede usar GPU")
        else:
            image_paths = [Path(p) for p in cp.get("image_paths", [])]
            clip_paths = [Path(p) for p in cp.get("clip_paths", [])]
            logger.info(f"[{job_id}] Fase GPU ya completada, saltando")

        # ════════════════════════════════════════
        # FASE CPU — sin lock (paralelo con otros jobs)
        # ════════════════════════════════════════

        # ── Paso 3: Concatenar clips ──
        raw_video = tmp / "raw_concat.mp4"
        if start_step < 3:
            logger.info(f"[{job_id}] Concatenando clips (CPU)...")
            editor.concat_clips(clip_paths, raw_video)
            _save_checkpoint(tmp, 3, image_paths=image_paths, clip_paths=clip_paths)

        # ── Paso 4: TTS ──
        narration_audio = tmp / "narration.wav"
        if start_step < 4:
            logger.info(f"[{job_id}] Generando narracion TTS (CPU)...")
            tts_engine.generate(decision.narration, narration_audio)
            _save_checkpoint(tmp, 4, image_paths=image_paths, clip_paths=clip_paths)

        # ── Paso 5: Mix audio ──
        with_audio = tmp / "with_audio.mp4"
        if start_step < 5:
            logger.info(f"[{job_id}] Mezclando audio (CPU)...")
            if MUSIC_PATH.exists():
                editor.mix_audio(raw_video, narration_audio, MUSIC_PATH, with_audio)
            else:
                # Sin música de fondo — solo narración
                logger.warning(f"[{job_id}] No hay música ({MUSIC_PATH}), solo narración")
                editor.mix_audio_no_music(raw_video, narration_audio, with_audio)
            _save_checkpoint(tmp, 5, image_paths=image_paths, clip_paths=clip_paths)

        # ── Paso 6: Subtítulos ──
        with_subs = tmp / "with_subs.mp4"
        if start_step < 6:
            logger.info(f"[{job_id}] Anadiendo subtitulos (CPU)...")
            editor.burn_subtitles(with_audio, decision.narration, narration_audio, with_subs)
            _save_checkpoint(tmp, 6, image_paths=image_paths, clip_paths=clip_paths)

        # ── Paso 7: Outro de marca ──
        final = tmp / "final.mp4"
        if start_step < 7:
            logger.info(f"[{job_id}] Anadiendo outro @finanzasjpg (CPU)...")
            editor.add_outro(with_subs, final)
            _save_checkpoint(tmp, 7, image_paths=image_paths, clip_paths=clip_paths)

        # ── Paso 8: Mover a pending ──
        output_path = Path(f"output/pending/{job_id}.mp4")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(final, output_path)

        logger.info(f"[{job_id}] Video generado: {output_path}")
        return output_path

    except Exception:
        logger.info(f"[{job_id}] Error — checkpoint guardado para reanudar")
        raise

    finally:
        output_path = Path(f"output/pending/{job_id}.mp4")
        if output_path.exists():
            shutil.rmtree(tmp, ignore_errors=True)
