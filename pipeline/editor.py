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
    music_volume: float = 0.12
) -> Path:
    """Mezcla vídeo + narración + música de fondo."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(narration_path),
        "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume=1.0[narr];"
        f"[2:a]volume={music_volume},aloop=loop=-1:size=2e+09[music];"
        f"[narr][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
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
    Quema subtítulos estilo TikTok en el vídeo.
    Divide el texto en chunks de 4-5 palabras.
    """
    audio_duration = get_duration(narration_audio_path)
    words = narration_text.split()
    chunk_size = 3  # 3 palabras por chunk — más legible en 15s
    chunks = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]

    time_per_chunk = audio_duration / len(chunks)

    # Generar fichero SRT
    srt_path = output_path.parent / "subs.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            start = i * time_per_chunk
            end = start + time_per_chunk
            text = " ".join(chunk).upper()
            f.write(f"{i+1}\n")
            f.write(f"{_fmt_time(start)} --> {_fmt_time(end)}\n")
            f.write(f"{text}\n\n")

    # Estilo subtítulos: blanco, negrita, sombra negra, centrado abajo
    subtitle_style = (
        "FontName=Arial,FontSize=28,Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "Outline=3,Shadow=1,"
        "Alignment=2,MarginV=80"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles={srt_path}:force_style='{subtitle_style}'",
        "-c:a", "copy",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    srt_path.unlink()
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
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
