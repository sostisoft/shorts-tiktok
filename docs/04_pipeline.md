# 04 — Pipeline de generación: FLUX → Wan2.1 → Kokoro → ffmpeg

## Flujo completo

```
Claude decide tema + prompts
    ↓
FLUX.1 schnell genera 8 imágenes (1 por escena)
    ↓
Wan2.1 I2V anima cada imagen → 8 clips de 3-5s
    ↓
Kokoro TTS genera narración en castellano
    ↓
ffmpeg:
  - Concatena los 8 clips
  - Ajusta duración al audio
  - Añade narración + música de fondo
  - Quema subtítulos estilo TikTok
  - Añade CTA final "Suscríbete 🔔"
  - Convierte a 1080x1920 vertical
    ↓
final.mp4 listo para YouTube Shorts
```

## Módulos

- `pipeline/image_gen.py` — FLUX.1 schnell (generación de imágenes)
- `pipeline/video_gen.py` — Wan2.1 I2V (animación imagen → vídeo)
- `pipeline/tts_engine.py` — Kokoro TTS (narración en castellano)
- `pipeline/editor.py` — ffmpeg (concatenación, audio, subtítulos, CTA)
- `pipeline/runner.py` — Orquestador del pipeline completo

Ver código completo en los ficheros fuente.
