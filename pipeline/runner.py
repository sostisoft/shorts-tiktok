import json
import shutil
import logging
import time
import gc
import threading
from pathlib import Path
from agents.orchestrator import VideoDecision
from pipeline.image_gen import ImageGenerator
from pipeline.image_bank import generate_with_cache, save_to_bank
from pipeline.video_gen import VideoGenerator
from pipeline.tts_engine import TTSEngine
from pipeline.music_gen import MusicGenerator
from pipeline import editor
from pipeline.timer import PipelineTimer

logger = logging.getLogger("videobot")

image_gen = ImageGenerator(model="schnell")
video_gen = VideoGenerator()
tts_engine = TTSEngine()
music_gen = MusicGenerator()

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
    Pipeline con checkpointing + GPU lock + logging con ETA.

    Fases GPU (con lock — 1 a la vez):
      - Paso 1: FLUX genera imágenes
      - Paso 2: Wan2.1 anima clips

    Fases CPU (sin lock — pueden correr en paralelo con otro job en GPU):
      - Paso 3: Concatenar clips (ffmpeg)
      - Paso 4: MusicGen (GPU)
      - Paso 5+: TTS + Mix + Subtítulos + Outro (ES + EN)

    Resultado: mientras Job A hace pasos 3+ en CPU, Job B puede hacer pasos 1-2 en GPU.
    """
    tmp = Path(f"output/tmp/{job_id}")
    tmp.mkdir(parents=True, exist_ok=True)

    cp = _load_checkpoint(tmp)
    start_step = cp.get("step", 0)

    timer = PipelineTimer(job_id)

    if start_step > 0:
        timer._log(f"Reanudando desde paso {start_step}")

    timer._log(f"Tiempo estimado total: ~{timer.estimated_total()}")

    try:
        prompts = decision.image_prompts[:3]
        img_dir = tmp / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        # ════════════════════════════════════════
        # FASE GPU — con lock (1 a la vez)
        # ════════════════════════════════════════

        if start_step < 2:
            timer._log("Esperando GPU lock...")
            with gpu_lock:
                timer._log("GPU lock adquirido")

                # ── Paso 1: Generar imágenes con FLUX ──
                if start_step < 1:
                    timer.start_phase("FLUX imagenes")
                    timer._log(f"Generando {len(prompts)} imagenes (FLUX schnell, 768x1344)...")
                    image_paths = image_gen.generate(prompts, job_id, img_dir)
                    _save_checkpoint(tmp, 1, image_paths=image_paths, clip_paths=[])
                    timer.end_phase("FLUX imagenes")
                else:
                    image_paths = [Path(p) for p in cp.get("image_paths", [])]
                    timer._log("Imagenes ya generadas, saltando")

                # Liberar FLUX de VRAM antes de cargar Wan2.1
                image_gen.unload()

                # ── Paso 2: Animar con Wan2.1 ──
                timer.start_phase("Wan2.1 animacion")
                timer._log(f"Animando {len(image_paths)} imagenes con Wan2.1 (GPU, 480x832, 10 steps)...")
                clip_paths = []
                for i, (img_path, prompt) in enumerate(zip(image_paths, prompts)):
                    clip_path = tmp / f"clip_{i:02d}.mp4"
                    if clip_path.exists() and clip_path.stat().st_size > 1000:
                        timer.log_subphase(f"Clip {i+1}/{len(prompts)} ya existe, saltando")
                        clip_paths.append(clip_path)
                        continue
                    tc = time.time()
                    video_gen.animate(img_path, prompt, clip_path, duration_seconds=5)
                    timer.log_subphase(f"Clip {i+1}/{len(prompts)}: {int(time.time()-tc)}s")
                    clip_paths.append(clip_path)
                _save_checkpoint(tmp, 2, image_paths=image_paths, clip_paths=clip_paths)
                timer.end_phase("Wan2.1 animacion")

                # Liberar Wan2.1 de VRAM
                video_gen.unload()

            timer._log("GPU lock liberado — otro job puede usar GPU")
        else:
            image_paths = [Path(p) for p in cp.get("image_paths", [])]
            clip_paths = [Path(p) for p in cp.get("clip_paths", [])]
            timer._log("Fase GPU ya completada, saltando")

        # ════════════════════════════════════════
        # FASE CPU — sin lock (paralelo con otros jobs)
        # ════════════════════════════════════════

        # ── Paso 3: Concatenar clips ──
        raw_video = tmp / "raw_concat.mp4"
        if start_step < 3:
            timer.start_phase("Concat clips")
            editor.concat_clips(clip_paths, raw_video)
            _save_checkpoint(tmp, 3, image_paths=image_paths, clip_paths=clip_paths)
            timer.end_phase("Concat clips")

        # ── Paso 4: Generar música única para este vídeo ──
        music_path = tmp / "music.wav"
        if start_step < 4:
            timer.start_phase("MusicGen")
            timer._log("Generando musica de fondo (MusicGen GPU)...")
            music_gen.generate(
                topic=decision.topic,
                style=decision.style,
                output_path=music_path,
                duration_seconds=17,
            )
            _save_checkpoint(tmp, 4, image_paths=image_paths, clip_paths=clip_paths)
            timer.end_phase("MusicGen")

        # ════════════════════════════════════════
        # Generar 2 versiones: ES + EN
        # Mismas imágenes/clips/música, distinta voz y subtítulos
        # ════════════════════════════════════════

        results = {}
        for lang, narration_text, voice, suffix in [
            ("es", decision.narration, "ef_dora", "es"),
            ("en", decision.narration_en, "af_sarah", "en"),
        ]:
            lang_upper = lang.upper()
            timer._log(f"=== Versión {lang_upper} ===")

            # TTS
            narration_audio = tmp / f"narration_{suffix}.wav"
            if not narration_audio.exists():
                timer.start_phase(f"TTS {lang_upper}")
                tts_engine.generate(narration_text, narration_audio, voice=voice)
                timer.end_phase(f"TTS {lang_upper}")

            # Mix audio (vídeo + narración + música)
            with_audio = tmp / f"with_audio_{suffix}.mp4"
            if not with_audio.exists():
                timer.start_phase(f"Mix audio {lang_upper}")
                editor.mix_audio(raw_video, narration_audio, music_path, with_audio)
                timer.end_phase(f"Mix audio {lang_upper}")

            # Subtítulos ASS
            with_subs = tmp / f"with_subs_{suffix}.mp4"
            if not with_subs.exists():
                timer.start_phase(f"Subtitulos {lang_upper}")
                editor.burn_subtitles(with_audio, narration_text, narration_audio, with_subs)
                timer.end_phase(f"Subtitulos {lang_upper}")

            # Outro de marca
            final = tmp / f"final_{suffix}.mp4"
            if not final.exists():
                timer.start_phase(f"Outro {lang_upper}")
                editor.add_outro(with_subs, final)
                timer.end_phase(f"Outro {lang_upper}")

            results[suffix] = final

        # ── Mover a pending ──
        output_es = Path(f"output/pending/{job_id}_es.mp4")
        output_en = Path(f"output/pending/{job_id}_en.mp4")
        output_es.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(results["es"], output_es)
        shutil.copy(results["en"], output_en)

        total_s = timer.finish()
        timer._log(f"Videos: {output_es} + {output_en}")
        return output_es

    except Exception:
        logger.info(f"[{job_id}] Error — checkpoint guardado para reanudar")
        raise

    finally:
        output_es = Path(f"output/pending/{job_id}_es.mp4")
        if output_es.exists():
            shutil.rmtree(tmp, ignore_errors=True)
