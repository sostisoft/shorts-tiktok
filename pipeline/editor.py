import subprocess
import json
from pathlib import Path


def get_duration(path: Path) -> float:
    """Obtiene duración de un fichero de audio/vídeo."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", str(path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return float(data["streams"][0]["duration"])


def concat_clips(clip_paths: list[Path], output_path: Path) -> Path:
    """Concatena múltiples clips MP4 en uno."""
    # Crear fichero de lista para ffmpeg concat
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip.absolute()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink()
    return output_path


def mix_audio(
    video_path: Path,
    narration_path: Path,
    music_path: Path,
    output_path: Path,
    music_volume: float = 0.15
) -> Path:
    """
    Mezcla vídeo + narración + música con audio profesional:
    - Loudnorm voz a -14 LUFS (estándar plataformas)
    - Sidechain compress: música baja cuando hay voz (ducking)
    - Loudnorm final de la mezcla
    """
    filter_complex = (
        # Normalizar voz a -14 LUFS
        "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[voice];"
        # Música baja + loop infinito
        f"[2:a]volume={music_volume},aloop=loop=-1:size=2e+09[music_quiet];"
        # Split voz para sidechain
        "[voice]asplit=2[sc][voice_out];"
        # Ducking: música baja cuando hay voz
        "[music_quiet][sc]sidechaincompress=threshold=0.02:ratio=6:attack=200:release=1000[music_ducked];"
        # Mezclar voz + música ducked
        "[voice_out][music_ducked]amix=inputs=2:duration=first:dropout_transition=2[audio_mix];"
        # Loudnorm final
        "[audio_mix]loudnorm=I=-14:TP=-1.5:LRA=11[audio_final]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(narration_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[audio_final]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def mix_audio_no_music(
    video_path: Path,
    narration_path: Path,
    output_path: Path,
) -> Path:
    """Mezcla vídeo + narración sin música de fondo."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(narration_path),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def burn_subtitles(
    video_path: Path,
    narration_text: str,
    narration_audio_path: Path,
    output_path: Path
) -> Path:
    """
    Quema subtítulos estilo TikTok con ASS: 3 palabras a la vez,
    Montserrat Bold, outline grueso, centrado en pantalla.
    """
    audio_duration = get_duration(narration_audio_path)
    words = narration_text.split()
    chunk_size = 3
    chunks = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]

    time_per_chunk = audio_duration / len(chunks)

    # Generar fichero ASS con estilo TikTok
    ass_path = output_path.parent / "subs.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write("PlayResX: 1080\n")
        f.write("PlayResY: 1920\n")
        f.write("WrapStyle: 0\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding\n")
        # Estilo principal: blanco, Montserrat Bold, outline negro grueso
        f.write("Style: Default,Montserrat,72,&H00FFFFFF,&H000000FF,"
                "&H00000000,&H80000000,1,0,0,0,"
                "100,100,2,0,1,4,0,"
                "5,40,40,400,1\n")
        # Estilo highlight: cian para palabra activa
        f.write("Style: Highlight,Montserrat,80,&H00FFFF00,&H000000FF,"
                "&H00000000,&H80000000,1,0,0,0,"
                "105,105,2,0,1,5,0,"
                "5,40,40,400,1\n\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

        for i, chunk in enumerate(chunks):
            start = i * time_per_chunk
            end = start + time_per_chunk
            text = " ".join(chunk).upper()
            start_ts = _fmt_ass_time(start)
            end_ts = _fmt_ass_time(end)
            # Alternar estilos para dar dinamismo visual
            style = "Highlight" if i % 2 == 0 else "Default"
            f.write(f"Dialogue: 0,{start_ts},{end_ts},{style},,0,0,0,,{text}\n")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"ass={ass_path}",
        "-c:a", "copy",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    ass_path.unlink()
    return output_path


def add_outro(video_path: Path, output_path: Path) -> Path:
    """
    Añade outro de marca fijo en los últimos 2 segundos.
    Siempre igual: @finanzasjpg centrado para que la gente asocie la marca.
    """
    duration = get_duration(video_path)
    outro_start = max(0, duration - 2)

    # Marca arriba + handle abajo — siempre el mismo cierre
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf",
        # Línea 1: nombre del canal
        f"drawtext=text='Finanzas Claras':"
        f"fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf:"
        f"fontsize=42:fontcolor=white:bordercolor=black:borderw=4:"
        f"x=(w-text_w)/2:y=h/2-40:"
        f"enable='between(t,{outro_start},{duration})',"
        # Línea 2: handle / @
        f"drawtext=text='@finanzasjpg':"
        f"fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf:"
        f"fontsize=28:fontcolor=yellow:bordercolor=black:borderw=3:"
        f"x=(w-text_w)/2:y=h/2+20:"
        f"enable='between(t,{outro_start},{duration})'",
        "-c:a", "copy",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _fmt_time(seconds: float) -> str:
    """Formato SRT: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_ass_time(seconds: float) -> str:
    """Formato ASS: H:MM:SS.cc (centésimas)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
