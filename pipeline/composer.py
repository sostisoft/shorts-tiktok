"""
pipeline/composer.py
Compositor final — simple y robusto.
Une clips, añade voz + música, quema subtítulos ASS estilo TikTok.
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

            # 3. Generar subtítulos ASS
            logger.info("Generando subtítulos ASS...")
            ass_path = tmp / "subtitles.ass"
            self._generate_ass_subtitles(subtitles, ass_path)

            # 4. Unir vídeo + audio + subtítulos
            logger.info("Compositing final...")
            self._final_compose(concat_video, mixed_audio, ass_path, output_path, target_duration)

        size_mb = output_path.stat().st_size / 1e6
        logger.info(f"Video final: {output_path} ({size_mb:.1f} MB)")
        return output_path

    def _concat_clips(self, clips: list[Path], output: Path):
        if len(clips) == 1:
            # Single clip — just copy without audio
            cmd = ["ffmpeg", "-y", "-i", str(clips[0]),
                   "-c:v", "copy", "-an", str(output)]
            self._run(cmd, "concat")
            return

        # Use xfade for smooth fade transitions between clips
        transition_dur = 0.3
        clip_dur = 5.0  # each clip is ~5 seconds

        # Build input args
        input_args = []
        for clip in clips:
            input_args += ["-i", str(clip)]

        # Build xfade filter chain
        filter_parts = []
        n = len(clips)

        # First xfade: [0:v][1:v] -> [v01]
        offset = clip_dur - transition_dur
        if n == 2:
            out_label = "out"
        else:
            out_label = "v01"
        filter_parts.append(
            f"[0:v][1:v]xfade=transition=fade:duration={transition_dur}:offset={offset:.4f}[{out_label}]"
        )

        # Chain remaining clips
        for i in range(2, n):
            prev_label = f"v{''.join(str(x) for x in range(i))}"
            offset += clip_dur - transition_dur
            if i == n - 1:
                out_label = "out"
            else:
                out_label = f"v{''.join(str(x) for x in range(i + 1))}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition=fade:duration={transition_dur}:offset={offset:.4f}[{out_label}]"
            )

        filter_complex = "; ".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-an",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(output),
        ]
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

    def _generate_ass_subtitles(self, words: list[dict], output_path: Path):
        """
        Genera un fichero ASS con subtítulos estilo TikTok: frases de 3-4 palabras
        con la palabra activa resaltada en amarillo (#FFD700) y las demás en blanco.

        Args:
            words: lista de dicts con claves "word", "start", "end" (timestamps de Whisper)
            output_path: ruta del fichero .ass a generar
        """
        if not words:
            # Empty ASS file so ffmpeg doesn't fail
            output_path.write_text(self._ass_header() + "\n")
            return

        words_per_phrase = 3
        phrases = []
        for i in range(0, len(words), words_per_phrase):
            phrase_words = words[i:i + words_per_phrase]
            phrases.append(phrase_words)

        events = []
        for phrase in phrases:
            phrase_texts = [w["word"] for w in phrase]
            # For each word in the phrase, create a dialogue line highlighting that word
            for active_idx, active_word in enumerate(phrase):
                start_ts = self._format_ass_time(active_word["start"])
                end_ts = self._format_ass_time(active_word["end"])

                # Build the text with override tags
                parts = []
                for j, w in enumerate(phrase):
                    if j == active_idx:
                        # Active word: Highlight style with pop effect
                        # \fscx110\fscy110 gives a slight pop, \rHighlight switches style
                        parts.append(
                            "{\\rHighlight\\fscx110\\fscy110}" + w["word"] + "{\\rDefault}"
                        )
                    else:
                        parts.append(w["word"])

                text = " ".join(parts)
                events.append(
                    f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}"
                )

        ass_content = self._ass_header() + "\n".join(events) + "\n"
        output_path.write_text(ass_content, encoding="utf-8")
        logger.info(f"ASS subtitles: {len(phrases)} phrases, {len(events)} events -> {output_path}")

    @staticmethod
    def _ass_header() -> str:
        """Devuelve la cabecera ASS con estilos TikTok."""
        return (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "WrapStyle: 0\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Montserrat Bold,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,4,2,2,40,40,350,1\n"
            "Style: Highlight,Montserrat Bold,54,&H0000D7FF,&H000000FF,&H00000000,&H80000000,"
            "-1,0,0,0,105,105,0,0,1,5,2,2,40,40,350,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """Convierte segundos a formato ASS: H:MM:SS.cc"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds % 1) * 100))
        if cs >= 100:
            cs = 99
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _final_compose(self, video: Path, audio: Path, ass_path: Path,
                       output: Path, duration: float | None):
        """Une vídeo escalado + audio + subtítulos ASS."""
        dur_flag = ["-t", str(duration)] if duration else []

        # Scale slightly larger + subtle floating drift effect + burn ASS subtitles
        # The ass filter must use escaped path (colons and backslashes)
        ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf = (
            "scale=1188:2112:force_original_aspect_ratio=increase"
            ",crop=1080:1920:x='(iw-1080)/2+sin(t*0.5)*20':y='(ih-1920)/2+cos(t*0.3)*15'"
            f",ass='{ass_escaped}'"
        )

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
    def build_subtitle_segments_from_narration(
        narration_text: str,
        total_duration: float,
        voice_path: str | Path | None = None,
        words_per_chunk: int = 3,
    ) -> list[dict]:
        """
        Genera timestamps palabra a palabra usando faster-whisper para alinear con el audio.

        Si voice_path se proporciona, usa Whisper para obtener timestamps reales.
        Si no, hace estimación uniforme como fallback.

        Returns:
            Lista de dicts con claves "word", "start", "end" para cada palabra.
        """
        if not narration_text:
            return []

        if voice_path is not None:
            try:
                return VideoComposer._whisper_word_timestamps(voice_path)
            except Exception as e:
                logger.warning(f"Whisper transcription failed, falling back to estimation: {e}")

        # Fallback: estimación uniforme (sin Whisper)
        logger.info("Using uniform time estimation for subtitles (no voice audio)")
        words = narration_text.split()
        if not words:
            return []
        dur_per_word = total_duration / len(words)
        return [
            {"word": w, "start": i * dur_per_word, "end": (i + 1) * dur_per_word}
            for i, w in enumerate(words)
        ]

    @staticmethod
    def _whisper_word_timestamps(audio_path: str | Path) -> list[dict]:
        """Usa openai-whisper para obtener timestamps palabra a palabra."""
        import whisper

        audio_path = Path(audio_path)
        logger.info(f"Transcribing with openai-whisper for word timestamps: {audio_path}")

        model = whisper.load_model("tiny", device="cpu")
        result = model.transcribe(str(audio_path), language="es", word_timestamps=True)

        words = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                w = word["word"].strip()
                if w:
                    words.append({"word": w, "start": word["start"], "end": word["end"]})

        if not words:
            raise ValueError("Whisper returned no words")

        logger.info(f"Whisper extracted {len(words)} words ({words[0]['start']:.2f}s - {words[-1]['end']:.2f}s)")
        return words

    @staticmethod
    def build_subtitle_segments_from_script(script_lines: list[str], total_duration: float) -> list[dict]:
        if not script_lines:
            return []
        dur_per = total_duration / len(script_lines)
        return [{"text": l, "start": i * dur_per, "end": (i + 1) * dur_per} for i, l in enumerate(script_lines)]
