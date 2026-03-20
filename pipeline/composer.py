"""
pipeline/composer.py
Compositor final — simple y robusto.
Une clips, añade voz + música, quema subtítulos con drawtext.
Output: 1080x1920, H.264, AAC 192k.
"""
import logging
import json
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("videobot.composer")


class VideoComposer:

    def compose(
        self,
        clips: list[Path],
        audio_voice: Path,
        audio_music: Path,
        subtitles: list[dict],
        output_path: str | Path,
        target_duration: float | None = None,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="videobot_") as tmp:
            tmp = Path(tmp)

            # 1. Concatenar clips
            logger.info(f"Concatenando {len(clips)} clips...")
            concat_video = tmp / "concat.mp4"
            self._concat_clips(clips, concat_video)

            # 2. Mezclar audio (voz + música)
            logger.info("Mezclando audio...")
            mixed_audio = tmp / "mixed.aac"
            self._mix_audio(audio_voice, audio_music, mixed_audio, target_duration)

            # 3. Unir vídeo + audio + subtítulos
            logger.info("Compositing final...")
            self._final_compose(concat_video, mixed_audio, subtitles, output_path, target_duration)

        size_mb = output_path.stat().st_size / 1e6
        logger.info(f"Video final: {output_path} ({size_mb:.1f} MB)")
        return output_path

    def _concat_clips(self, clips: list[Path], output: Path):
        list_file = output.parent / "clips.txt"
        with open(list_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip.resolve()}'\n")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", str(list_file), "-c:v", "copy", "-an", str(output)]
        self._run(cmd, "concat")

    def _mix_audio(self, voice: Path, music: Path, output: Path, duration: float | None):
        """Mezcla voz + música. Música al 15% de volumen."""
        dur_flag = ["-t", str(duration)] if duration else []
        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice),
            "-i", str(music),
            *dur_flag,
            "-filter_complex",
            "[0:a]aresample=44100[v];[1:a]aresample=44100,volume=0.15[m];[v][m]amix=inputs=2:duration=first[out]",
            "-map", "[out]",
            "-c:a", "aac", "-b:a", "192k",
            str(output),
        ]
        self._run(cmd, "mix audio")

    def _final_compose(self, video: Path, audio: Path, subtitles: list[dict],
                       output: Path, duration: float | None):
        """Une vídeo escalado + audio + subtítulos drawtext."""
        dur_flag = ["-t", str(duration)] if duration else []

        # Construir filtro de subtítulos con drawtext
        # Cada chunk se muestra en su tiempo con enable='between(t,start,end)'
        vf_parts = ["scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"]

        for seg in subtitles:
            text = seg["text"].replace("'", "'\\''").replace(":", "\\:")
            start = seg["start"]
            end = seg["end"]
            vf_parts.append(
                f"drawtext=text='{text}'"
                f":fontfile=/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf"
                f":fontsize=42:fontcolor=white:borderw=3:bordercolor=black"
                f":x=(w-text_w)/2:y=h-h/6"
                f":enable='between(t,{start:.2f},{end:.2f})'"
            )

        vf = ",".join(vf_parts)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(audio),
            *dur_flag,
            "-vf", vf,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output),
        ]
        self._run(cmd, "compose")

    @staticmethod
    def _run(cmd: list[str], step: str):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg [{step}] error:\n{result.stderr[-1000:]}")
            raise RuntimeError(f"FFmpeg falló en '{step}' (código {result.returncode})")

    @staticmethod
    def get_video_duration(path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True, text=True,
        )
        return float(json.loads(result.stdout)["format"]["duration"])

    @staticmethod
    def build_subtitle_segments_from_narration(narration_text: str, total_duration: float, words_per_chunk: int = 3) -> list[dict]:
        """Divide narración en chunks de N palabras sincronizados con la duración."""
        if not narration_text:
            return []
        words = narration_text.split()
        chunks = [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)]
        if not chunks:
            return []
        dur_per = total_duration / len(chunks)
        return [{"text": c, "start": i * dur_per, "end": (i + 1) * dur_per} for i, c in enumerate(chunks)]

    @staticmethod
    def build_subtitle_segments_from_script(script_lines: list[str], total_duration: float) -> list[dict]:
        if not script_lines:
            return []
        dur_per = total_duration / len(script_lines)
        return [{"text": l, "start": i * dur_per, "end": (i + 1) * dur_per} for i, l in enumerate(script_lines)]
