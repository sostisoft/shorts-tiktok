from pathlib import Path
import shutil
import logging
from agents.orchestrator import VideoDecision
from pipeline.image_gen import ImageGenerator
from pipeline.video_gen import VideoGenerator
from pipeline.tts_engine import TTSEngine
from pipeline import editor

logger = logging.getLogger("videobot")

image_gen = ImageGenerator()   # Se carga una vez, se reutiliza
video_gen = VideoGenerator()
tts_engine = TTSEngine()

MUSIC_PATH = Path("assets/music/finance_background.mp3")


def generate_video(decision: VideoDecision, job_id: str) -> Path:
    """
    Pipeline completo: decisión → vídeo final.
    Devuelve ruta del MP4 final.
    """
    tmp = Path(f"output/tmp/{job_id}")
    tmp.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Generar imágenes con FLUX
        logger.info(f"[{job_id}] Generando {len(decision.image_prompts)} imágenes...")
        img_dir = tmp / "images"
        image_paths = image_gen.generate(decision.image_prompts, job_id, img_dir)

        # 2. Animar cada imagen con Wan2.1
        logger.info(f"[{job_id}] Animando imágenes con Wan2.1...")
        clip_paths = []
        for i, (img_path, prompt) in enumerate(zip(image_paths, decision.image_prompts)):
            clip_path = tmp / f"clip_{i:02d}.mp4"
            video_gen.animate(img_path, prompt, clip_path, duration_seconds=5)
            clip_paths.append(clip_path)

        # 3. Concatenar clips
        logger.info(f"[{job_id}] Concatenando clips...")
        raw_video = tmp / "raw_concat.mp4"
        editor.concat_clips(clip_paths, raw_video)

        # 4. Generar narración con Kokoro
        logger.info(f"[{job_id}] Generando narración TTS...")
        narration_audio = tmp / "narration.wav"
        tts_engine.generate(decision.narration, narration_audio)

        # 5. Mezclar audio
        logger.info(f"[{job_id}] Mezclando audio...")
        with_audio = tmp / "with_audio.mp4"
        editor.mix_audio(raw_video, narration_audio, MUSIC_PATH, with_audio)

        # 6. Quemar subtítulos
        logger.info(f"[{job_id}] Añadiendo subtítulos...")
        with_subs = tmp / "with_subs.mp4"
        editor.burn_subtitles(with_audio, decision.narration, narration_audio, with_subs)

        # 7. Añadir CTA
        logger.info(f"[{job_id}] Añadiendo CTA...")
        final = tmp / "final.mp4"
        editor.add_cta(with_subs, final)

        # 8. Mover a output/pending
        output_path = Path(f"output/pending/{job_id}.mp4")
        shutil.copy(final, output_path)

        logger.info(f"[{job_id}] Vídeo generado: {output_path}")
        return output_path

    finally:
        # Limpiar tmp (mantener solo el final)
        if (tmp / "final.mp4").exists():
            shutil.rmtree(tmp, ignore_errors=True)
