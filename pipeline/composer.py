"""
pipeline/composer.py
Compositor final con FFmpeg.
- Une clips de video animados por Wan2GP
- Añade voz TTS con loudnorm
- Añade música con sidechain ducking (baja cuando habla)
- Quema subtítulos ASS estilo TikTok (palabra por palabra)
- Output: 1080×1920 MP4, H.264, AAC 192k, faststart
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import pysubs2

logger = logging.getLogger("videobot.composer")

# Fuente y estilo para subtítulos (estilo TikTok/Shorts)
SUBTITLE_STYLE = {
    "fontname": "Montserrat",
    "fontsize": 72,
    "bold": True,
    "primarycolor": "&H00FFFFFF",    # blanco
    "outlinecolor": "&H00000000",    # negro
    "backcolor": "&H80000000",       # semitransparente
    "outline": 3,
    "shadow": 2,
    "alignment": 2,                  # center-bottom
    "marginv": 120,                  # margen inferior
}


class VideoComposer:
    """
    Ensambla el video final desde los componentes generados por el pipeline.
    """

    def compose(
        self,
        clips: list[Path],
        audio_voice: Path,
        audio_music: Path,
        subtitles: list[dict],        # [{"text": "...", "start": 0.0, "end": 1.2}, ...]
        output_path: str | Path,
        target_duration: float | None = None,
    ) -> Path:
        """
        Ensambla el video final.

        Args:
            clips:           Lista de .mp4 generados por Wan2GP (5s cada uno)
            audio_voice:     .wav de la voz TTS
            audio_music:     .wav de la música de fondo
            subtitles:       Lista de segmentos con texto y timings
            output_path:     Ruta del .mp4 final
            target_duration: Duración objetivo en segundos (None = duración del audio)

        Returns:
            Path al .mp4 final
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="videobot_compose_") as tmp:
            tmp = Path(tmp)

            # 1. Concatenar clips de video
            logger.info(f"Concatenando {len(clips)} clips...")
            concat_video = tmp / "concat.mp4"
            self._concat_clips(clips, concat_video)

            # 2. Generar fichero ASS de subtítulos
            logger.info("Generando subtítulos ASS...")
            ass_path = tmp / "subtitles.ass"
            self._build_ass(subtitles, ass_path)

            # 3. Compositing final con FFmpeg
            logger.info("Compositing final (FFmpeg)...")
            self._ffmpeg_compose(
                video=concat_video,
                voice=audio_voice,
                music=audio_music,
                ass=ass_path,
                output=output_path,
                target_duration=target_duration,
            )

        logger.info(f"Video final: {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")
        return output_path

    # ── Concatenación de clips ────────────────────────────────────────────────

    def _concat_clips(self, clips: list[Path], output: Path):
        """Concatena clips MP4 con FFmpeg concat demuxer."""
        list_file = output.parent / "clip_list.txt"
        with open(list_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip.resolve()}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "copy",
            "-an",                  # sin audio — lo añadimos después
            str(output),
        ]
        self._run(cmd, "concat clips")

    # ── Subtítulos ASS ────────────────────────────────────────────────────────

    def _build_ass(self, segments: list[dict], output: Path):
        """
        Genera fichero .ass con estilo TikTok: una o dos palabras por tarjeta,
        en negrita, centradas abajo, con outline negro.
        """
        subs = pysubs2.SSAFile()

        # Sobrescribir estilo Default
        style = subs.styles["Default"]
        for key, value in SUBTITLE_STYLE.items():
            if hasattr(style, key):
                setattr(style, key, value)

        for seg in segments:
            text = seg.get("text", "").strip()
            start_ms = int(seg.get("start", 0) * 1000)
            end_ms = int(seg.get("end", start_ms / 1000 + 2) * 1000)
            if not text:
                continue

            # Dividir en grupos de 2-3 palabras para efecto TikTok
            words = text.split()
            chunk_size = 3
            chunks = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]
            chunk_duration = (end_ms - start_ms) // max(len(chunks), 1)

            for i, chunk in enumerate(chunks):
                line = pysubs2.SSAEvent(
                    start=start_ms + i * chunk_duration,
                    end=start_ms + (i + 1) * chunk_duration,
                    text=" ".join(chunk).upper(),
                )
                subs.append(line)

        subs.save(str(output))
        logger.info(f"Subtítulos ASS generados: {len(subs)} eventos → {output}")

    # ── FFmpeg compositing ────────────────────────────────────────────────────

    def _ffmpeg_compose(
        self,
        video: Path,
        voice: Path,
        music: Path,
        ass: Path,
        output: Path,
        target_duration: float | None,
    ):
        """
        FFmpeg: video + voz (loudnorm) + música (sidechain ducking) + subtítulos.
        Output: 1080×1920, H.264 High Profile, CRF 18, AAC 192k, faststart.
        """
        # Duración: la de la voz si no se especifica
        duration_flag = ["-t", str(target_duration)] if target_duration else []

        # Audio chain:
        # [0:a] = voz TTS  → loudnorm → [voice_n]
        # [1:a] = música   → volume=0.25 → adelay según inicio → [music_d]
        # [voice_n][music_d] → amix → [audio_out]
        #
        # Sidechain ducking via sidechaincompress:
        # Baja la música cuando la voz supera -20 dBFS

        audio_filter = (
            "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[voice_n];"
            "[1:a]volume=0.20[music_raw];"
            "[music_raw][voice_n]sidechaincompress="
            "threshold=0.02:ratio=4:attack=100:release=1000[music_d];"
            "[voice_n][music_d]amix=inputs=2:duration=first:dropout_transition=2[audio_out]"
        )

        # Video: escalar a 1080×1920, quemar subtítulos
        video_filter = (
            f"[2:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"ass={ass}[vout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice),
            "-i", str(music),
            "-i", str(video),
            *duration_flag,
            "-filter_complex", f"{audio_filter};{video_filter}",
            "-map", "[vout]",
            "-map", "[audio_out]",
            # Video encoding
            "-c:v", "libx264",
            "-profile:v", "high",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "24",
            # Audio encoding
            "-c:a", "aac",
            "-b:a", "192k",
            "-ac", "2",
            "-ar", "44100",
            # Container
            "-movflags", "+faststart",
            str(output),
        ]
        self._run(cmd, "ffmpeg compose")

    # ── Utilidades ────────────────────────────────────────────────────────────

    @staticmethod
    def _run(cmd: list[str], step: str):
        logger.debug(f"FFmpeg [{step}]: {' '.join(cmd[:6])}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg [{step}] error:\n{result.stderr[-2000:]}")
            raise RuntimeError(f"FFmpeg falló en paso '{step}' (código {result.returncode})")

    @staticmethod
    def get_video_duration(path: Path) -> float:
        """Devuelve la duración en segundos de un vídeo."""
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True,
        )
        import json
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    @staticmethod
    def build_subtitle_segments_from_script(script_lines: list[str], total_duration: float) -> list[dict]:
        """
        Distribuye líneas de guión uniformemente en el tiempo.
        Para timing real, usar whisper-timestamped sobre el audio TTS.
        """
        if not script_lines:
            return []
        duration_per = total_duration / len(script_lines)
        segments = []
        for i, line in enumerate(script_lines):
            segments.append({
                "text": line,
                "start": i * duration_per,
                "end": (i + 1) * duration_per,
            })
        return segments
