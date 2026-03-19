# 04 — Pipeline de Generacion de Video

Pipeline completo que transforma un tema de finanzas personales en un YouTube Short listo para publicar.
Todo corre en local sobre el GMKtec EVO-X2 (Ryzen AI MAX+ 395, 128 GB UMA, Radeon 8060S gfx1151).

---

## Diagrama de flujo

```
                          ┌─────────────────────────────────────┐
                          │         ENTRADA (tema/topic)         │
                          └──────────────┬──────────────────────┘
                                         │
                          ┌──────────────▼──────────────────────┐
                          │  1. GUION (ScriptAgent / Ollama)     │
                          │     Qwen 2.5 14B → JSON con:        │
                          │     title, narration, scenes[],      │
                          │     image_prompts[], tags[]           │
                          └──────────────┬──────────────────────┘
                                         │
                     ┌───────────────────▼───────────────────┐
                     │  2. IMAGENES (FLUX.1-schnell)  [GPU]  │
                     │     N escenas → N imagenes PNG         │
                     │     768x1344 o 576x1024 (segun path)   │
                     └───────────────────┬───────────────────┘
                                         │  unload FLUX
                     ┌───────────────────▼───────────────────┐
                     │  3. VIDEO (Wan2.1 I2V 14B)    [GPU]   │
                     │     N imagenes → N clips MP4 @16fps    │
                     │     480x832, 81 frames, 10 steps       │
                     └───────────────────┬───────────────────┘
                                         │  unload Wan2.1
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
   ┌──────────▼──────────┐  ┌───────────▼──────────┐  ┌───────────▼──────────┐
   │ 4. TTS       [CPU]  │  │ 5. MUSICA    [CPU]   │  │ 3b. CONCAT   [CPU]   │
   │ Chatterbox/Kokoro   │  │ MusicGen small       │  │ ffmpeg concat        │
   │ → voice.wav 24kHz   │  │ → music.wav 32kHz    │  │ → raw_concat.mp4     │
   └──────────┬──────────┘  └───────────┬──────────┘  └───────────┬──────────┘
              │                          │                          │
              └──────────────────────────┼──────────────────────────┘
                                         │
                     ┌───────────────────▼───────────────────┐
                     │  6. COMPOSITING (FFmpeg)      [CPU]   │
                     │     - Escalar a 1080x1920             │
                     │     - loudnorm voz (-16 LUFS)         │
                     │     - Sidechain ducking musica         │
                     │     - Subtitulos ASS (TikTok style)    │
                     │     - Outro @finanzasjpg               │
                     │     → H.264 High, CRF 18, AAC 192k    │
                     └───────────────────┬───────────────────┘
                                         │
                          ┌──────────────▼──────────────────────┐
                          │       output/pending/{id}.mp4        │
                          │     (registrado en SQLite como       │
                          │      VideoStatus.PENDING)            │
                          └─────────────────────────────────────┘
```

---

## Dos rutas de ejecucion

El proyecto tiene **dos runners** con filosofias distintas:

### Ruta A: `scheduler/runner.py` (entrada principal)

Llamado desde `main.py` y `run.sh`. Usa **ScriptAgent** para generar el guion con Ollama.

```
main.py → scheduler/runner.py → _run_generation_pipeline()
```

| Caracteristica         | Detalle                                                    |
|------------------------|------------------------------------------------------------|
| Guion                  | `ScriptAgent.generate()` via Ollama (Qwen 2.5 14B)        |
| Imagenes               | `ImageGenerator.generate_batch()` — carga unica de FLUX   |
| Video                  | `VideoGenerator.animate()` — clip por clip                 |
| TTS                    | `TTSGenerator` (Chatterbox con fallback a Kokoro)          |
| Musica                 | `MusicGenerator` (~duracion voz + 3s)                      |
| Compositing            | `VideoComposer.compose()` — subtitulos via pysubs2         |
| Checkpointing          | No — si falla, se repite todo                              |
| GPU lock               | No                                                         |
| DB                     | Si — registra en SQLite antes de terminar                  |
| Idiomas                | 1 (ES)                                                     |
| Publicacion            | Via `_publish_next_pending()` → YouTube API                |
| Generacion nocturna    | `night_generation_loop()` entre 00:00–06:00                |
| Max videos por noche   | 6 (configurable via `MAX_VIDEOS_PER_NIGHT`)                |

**Funciones publicas:**

```python
generate_only()           # Genera 1 video → output/pending/
publish_only()            # Publica siguiente pendiente en YouTube
night_generation_loop()   # Bucle nocturno automatico
run_job()                 # Genera + publica (modo test)
```

### Ruta B: `pipeline/runner.py` (con checkpointing)

Usa **VideoDecision** (del agente orquestador) y tiene checkpointing para reanudar.

```
agents/orchestrator.py → pipeline/runner.py → generate_video()
```

| Caracteristica         | Detalle                                                        |
|------------------------|----------------------------------------------------------------|
| Guion                  | Recibe `VideoDecision` ya generada por el orquestador          |
| Imagenes               | `ImageGenerator` + `image_bank` (cache con similitud >50%)     |
| Video                  | `VideoGenerator.animate()` con skip de clips existentes        |
| TTS                    | `TTSEngine` (Kokoro ONNX directamente)                         |
| Musica                 | `MusicGenerator` con topic y style del decision                |
| Compositing            | `editor.py` funciones sueltas (concat, mix, subs, outro)       |
| Checkpointing          | Si — `checkpoint.json` en `output/tmp/{job_id}/`              |
| GPU lock               | Si — `FileLock` basado en `output/.gpu_lock` (via fcntl)       |
| DB                     | No directamente (lo hace el orquestador)                       |
| Idiomas                | 2 (ES + EN) — mismos clips, distinta voz y subs               |
| Banco de imagenes      | Si — `assets/image-bank/` con indice JSON y reutilizacion      |

**Fases con lock:**

```
GPU LOCK (1 job a la vez):
  Paso 1: FLUX genera imagenes
  Paso 2: Wan2.1 anima clips
GPU LOCK LIBERADO

CPU (paralelo con otros jobs en GPU):
  Paso 3: Concatenar clips (ffmpeg)
  Paso 4: MusicGen
  Paso 5+: TTS + Mix + Subtitulos + Outro (x2 idiomas)
```

**Checkpoint:** se guarda en `output/tmp/{job_id}/checkpoint.json` con el numero de paso completado y las rutas de imagenes/clips. Si el proceso se interrumpe, al reiniciar salta los pasos ya completados.

---

## Cada paso en detalle

### Paso 1 — Generacion de imagenes (FLUX.1-schnell)

| Parametro     | Valor por defecto            | Env var               |
|---------------|------------------------------|-----------------------|
| Modelo        | `black-forest-labs/FLUX.1-schnell` | `FLUX_MODEL_ID`  |
| Ruta local    | `models/flux-schnell`        | `FLUX_LOCAL_PATH`     |
| Resolucion    | 1080x1920 (single) / 576x1024 (scheduler) / 768x1344 (pipeline) | parametro |
| Steps         | 4                            | parametro             |
| Guidance      | 0.0 (schnell no usa guidance)| parametro             |
| Dtype         | bfloat16                     | —                     |
| Tiempo est.   | ~20s por imagen (60s total para 3) | —              |
| VRAM          | ~12 GB                       | —                     |

**Fichero:** `pipeline/image_gen.py`

Carga el modelo con `FluxPipeline.from_pretrained()`, genera, y descarga inmediatamente con `del pipe + gc.collect() + torch.cuda.empty_cache()`. Nunca usa `enable_model_cpu_offload()` porque causa SVM thrashing en UMA.

El `generate_batch()` mantiene el modelo cargado durante todo el batch para evitar la sobrecarga de carga/descarga por imagen.

**Banco de imagenes** (`pipeline/image_bank.py`): antes de generar, busca en `assets/image-bank/` una imagen con >50% similitud de keywords financieras (Jaccard). Maximo 1 imagen cacheada por video. Las nuevas se guardan en el banco para futuro.

### Paso 2 — Animacion de video (Wan2.1 I2V 14B)

| Parametro     | Valor                        |
|---------------|------------------------------|
| Modelo        | `models/wan21` (local)       |
| Resolucion    | 480x832 (9:16 portrait)     |
| Frames        | 81 (5s @ 16fps)             |
| Steps         | 10                           |
| Guidance      | 5.0                          |
| Dtype         | bfloat16                     |
| Attention     | Flash/mem-efficient (SDP)    |
| VAE           | Tiling habilitado            |
| Tiempo est.   | ~80s por clip (240s total para 3) |
| VRAM          | ~40-50 GB                    |

**Fichero:** `pipeline/video_gen.py`

Usa `WanImageToVideoPipeline` de diffusers. Fuerza `enable_flash=True, enable_mem_efficient=True, enable_math=False` via `torch.backends.cuda.sdp_kernel` para evitar materializar la matriz de atencion completa (que consumiria ~160 GB).

Los frames se exportan directamente a ffmpeg via pipe stdin (sin escribir PNGs intermedios a disco) con `libx264 CRF 18`.

El prompt de movimiento se construye con prefijo cinematico: `"smooth cinematic camera movement, subtle motion, professional documentary style, {prompt}"`.

### Paso 3 — TTS (Text-to-Speech)

Hay **dos motores TTS** segun la ruta:

#### `pipeline/tts.py` — TTSGenerator (ruta scheduler)

| Parametro     | Valor                        | Env var               |
|---------------|------------------------------|-----------------------|
| Motor ppal.   | Chatterbox TTS               | —                     |
| Fallback      | Kokoro (via `kokoro.KPipeline`) | —                  |
| Ultimo recurso| Silencio (len(text)/15 segs) | —                     |
| Device        | CPU siempre                  | —                     |
| Sample rate   | 24000 Hz                     | —                     |
| Voz defecto   | "es" (espanol neutro)        | `TTS_VOICE`           |
| Clonacion     | Si (audio_prompt_path)       | `TTS_VOICE_SAMPLE`    |
| Expresividad  | 0.3 (profesional neutro)     | parametro             |
| Velocidad     | 1.0                          | parametro             |
| Tiempo est.   | ~3-5s                        | —                     |

#### `pipeline/tts_engine.py` — TTSEngine (ruta pipeline)

| Parametro     | Valor                        |
|---------------|------------------------------|
| Motor         | Kokoro ONNX                  |
| Ficheros      | `kokoro-v1.0.onnx` + `voices.bin` |
| Voces         | `ef_dora` (femenina), `em_alex` (masculino), `af_sarah` (EN) |
| Velocidad     | 1.1 (ligeramente rapido)    |
| Idioma        | "es" (espanol)               |
| Tiempo est.   | ~3s                          |

Ambos corren en CPU para no competir con la GPU durante generacion de video.

### Paso 4 — Musica de fondo (MusicGen)

| Parametro     | Valor                        | Env var               |
|---------------|------------------------------|-----------------------|
| Modelo        | `facebook/musicgen-small`    | `MUSIC_MODEL`         |
| Device        | CPU por defecto              | `MUSIC_DEVICE`        |
| Duracion      | ~35s (o voz + 3s)           | parametro             |
| Guidance      | 3.0                          | —                     |
| Sample rate   | 32 kHz                       | —                     |
| Tiempo est.   | ~45s                         | —                     |

**Fichero:** `pipeline/music_gen.py`

Genera musica instrumental sin vocales. Tiene 5 prompts tematicos de finanzas que se eligen aleatoriamente si no se especifica uno. El modelo se descarga de VRAM tras cada uso.

Formula de tokens: `max_new_tokens = duration_seconds * 50`.

### Paso 5 — Compositing final (FFmpeg)

Dos implementaciones segun la ruta:

#### `pipeline/composer.py` — VideoComposer (ruta scheduler)

Pipeline FFmpeg en un solo comando:

1. **Concatenar clips** — FFmpeg concat demuxer (`-f concat`)
2. **Subtitulos ASS** — Generados con `pysubs2`, estilo TikTok:
   - Montserrat Bold 72pt, blanco con outline negro
   - 2-3 palabras por tarjeta, en mayusculas
   - Alignment center-bottom, margen inferior 120
3. **Audio:**
   - Voz: `loudnorm I=-16:TP=-1.5:LRA=11`
   - Musica: `volume=0.20` + sidechain compress (`threshold=0.02:ratio=4`)
   - Mezcla: `amix inputs=2 duration=first`
4. **Video:**
   - Escalar a 1080x1920 (`scale + crop`)
   - Quemar subtitulos ASS
5. **Output:** H.264 High Profile, CRF 18, fast preset, AAC 192k, 44.1kHz, faststart

#### `pipeline/editor.py` — Funciones sueltas (ruta pipeline)

Misma logica pero en funciones independientes:

- `concat_clips()` — Concatena clips MP4
- `mix_audio()` — Voz (loudnorm -14 LUFS) + musica (ducking ratio=6) + loudnorm final
- `mix_audio_no_music()` — Solo voz sin musica
- `burn_subtitles()` — ASS con 2 estilos alternados (Default blanco + Highlight cian)
- `add_outro()` — Drawtext "Finanzas Claras" + "@finanzasjpg" en ultimos 2s

Diferencia clave: `editor.py` aplica loudnorm a -14 LUFS (estandar plataformas) vs `composer.py` que usa -16 LUFS. Tambien `editor.py` incluye un paso de loudnorm final sobre la mezcla.

---

## Gestion de memoria (128 GB UMA)

La memoria es unificada (CPU + GPU comparten los 128 GB). Los modelos se cargan y descargan **secuencialmente** para evitar picos:

```
Estado inicial: ~8 GB (sistema + Ollama idle)

Paso 1 — FLUX.1-schnell
  ├── _load():  +12 GB  → ~20 GB total
  ├── genera imagenes
  └── _unload(): -12 GB → ~8 GB
      del pipe + gc.collect() + torch.cuda.empty_cache()

Paso 2 — Wan2.1 I2V 14B
  ├── _load():  +45 GB  → ~53 GB total
  │   attention_slicing("auto") + vae.enable_tiling()
  ├── genera clips (pico ~60 GB con flash attention)
  └── unload(): -45 GB  → ~8 GB
      del pipe + gc.collect() + torch.cuda.empty_cache()

Paso 3 — TTS (Chatterbox/Kokoro)
  ├── CPU only: ~2 GB RAM, 0 GB VRAM
  └── No necesita descarga explicita

Paso 4 — MusicGen small
  ├── _load():  +1.5 GB → ~10 GB total (en CPU por defecto)
  ├── genera musica
  └── _unload(): -1.5 GB → ~8 GB

Paso 5 — FFmpeg
  └── Procesos externos, ~500 MB RAM
```

**Reglas criticas para UMA / Strix Halo:**

1. **NUNCA** usar `enable_model_cpu_offload()` — causa SVM thrashing catastrofico
2. **SIEMPRE** usar `pipe.to("cuda")` — en UMA "cuda" y "cpu" comparten la misma RAM
3. **SIEMPRE** descargar antes de cargar el siguiente: `del pipe` + `gc.collect()` + `torch.cuda.empty_cache()`
4. `HSA_ENABLE_SDMA=0` es obligatorio en APU
5. Flash attention obligatorio para Wan2.1 (sin ella, la atencion materializa ~160 GB)
6. TTM pages_limit=32505856 (124 GB GTT)

**GPU lock** (solo ruta pipeline/runner.py): usa `fcntl.flock()` sobre `output/.gpu_lock` para que solo un job tenga la GPU a la vez (pasos 1 y 2). Los pasos CPU (3+) corren sin lock, permitiendo que otro job tome la GPU.

---

## Estructura de directorios

```
output/
├── tmp/                          # Trabajo temporal por job
│   └── {job_id}/
│       ├── checkpoint.json       # Estado para reanudar (solo pipeline/runner.py)
│       ├── images/
│       │   ├── img_00.png
│       │   ├── img_01.png
│       │   └── img_02.png
│       ├── clip_00.mp4           # Clips animados
│       ├── clip_01.mp4
│       ├── clip_02.mp4
│       ├── raw_concat.mp4        # Clips concatenados sin audio
│       ├── music.wav             # Musica generada
│       ├── narration_es.wav      # Voz espanol
│       ├── narration_en.wav      # Voz ingles (solo pipeline/runner.py)
│       ├── with_audio_es.mp4     # Video + audio mezclado
│       ├── with_subs_es.mp4      # Video + subtitulos
│       ├── final_es.mp4          # Video final con outro
│       └── final_en.mp4          # Version ingles
│
├── pending/                      # Videos listos para publicar
│   ├── {job_id}.mp4              # (ruta scheduler: 1 fichero)
│   ├── {job_id}_es.mp4           # (ruta pipeline: 2 ficheros)
│   └── {job_id}_en.mp4
│
├── published/                    # Videos ya publicados (movidos desde pending)
│   └── {job_id}.mp4
│
└── .gpu_lock                     # Lock para coordinar GPU entre jobs

assets/
├── image-bank/                   # Cache de imagenes generadas
│   ├── index.json                # Indice con prompts y keywords
│   └── {fecha}_{hash}.png       # Imagenes guardadas
│
└── music/
    └── finance_background.mp3    # Musica de fallback estatica
```

El directorio `output/tmp/{job_id}/` se elimina automaticamente una vez que el video final se copia a `output/pending/`. Si el proceso falla, el checkpoint queda en tmp para reanudar.

---

## Ejecucion individual de pasos (debug)

Para depurar un paso concreto sin ejecutar todo el pipeline:

### Generar una imagen

```python
from pipeline.image_gen import ImageGenerator

gen = ImageGenerator(model="schnell")
path = gen.generate_single(
    prompt="professional office desk with laptop showing stock charts",
    output_path="test_image.png",
    width=768, height=1344,
    steps=4,
)
# FLUX se descarga automaticamente al terminar
```

### Animar una imagen

```python
from pipeline.video_gen import VideoGenerator
from pathlib import Path

vg = VideoGenerator()
vg.animate(
    image_path=Path("test_image.png"),
    prompt="slow zoom in, cinematic motion",
    output_path=Path("test_clip.mp4"),
    duration_seconds=5,
)
vg.unload()  # Liberar ~45 GB
```

### Generar voz TTS

```python
# Opcion 1: Chatterbox (con fallback)
from pipeline.tts import TTSGenerator
tts = TTSGenerator()
tts.generate("Hoy te explico como ahorrar mil euros al mes.", Path("test_voice.wav"))

# Opcion 2: Kokoro ONNX directo
from pipeline.tts_engine import TTSEngine
engine = TTSEngine()
engine.generate("Texto de prueba", Path("test_voice.wav"), voice="ef_dora")
```

### Generar musica

```python
from pipeline.music_gen import MusicGenerator

mg = MusicGenerator(device="cpu")  # o "cuda"
mg.generate(
    prompt="upbeat corporate electronic, no vocals",
    duration_seconds=30,
    output_path="test_music.wav",
)
```

### Compositing manual con editor.py

```python
from pipeline import editor
from pathlib import Path

# Concatenar clips
editor.concat_clips(
    [Path("clip_00.mp4"), Path("clip_01.mp4")],
    Path("concat.mp4")
)

# Mix audio con ducking
editor.mix_audio(
    Path("concat.mp4"),
    Path("voice.wav"),
    Path("music.wav"),
    Path("mixed.mp4"),
    music_volume=0.15,
)

# Quemar subtitulos
editor.burn_subtitles(
    Path("mixed.mp4"),
    "Texto completo de la narracion",
    Path("voice.wav"),
    Path("with_subs.mp4"),
)

# Outro
editor.add_outro(Path("with_subs.mp4"), Path("final.mp4"))
```

---

## Sistema PipelineTimer

**Fichero:** `pipeline/timer.py`

Trackea progreso con barras visuales, ETA y estimaciones por fase. Solo lo usa `pipeline/runner.py`.

### Estimaciones por defecto (segundos)

| Fase                | Estimacion | Peso (%) |
|---------------------|------------|----------|
| FLUX imagenes       | 60s        | 15/92 (16%) |
| Wan2.1 animacion    | 240s       | 50/92 (54%) |
| Concat clips        | 3s         | 1/92 (1%)   |
| MusicGen            | 45s        | 10/92 (11%) |
| TTS ES              | 3s         | 1/92 (1%)   |
| Mix audio ES        | 8s         | 2/92 (2%)   |
| Subtitulos ES       | 15s        | 3/92 (3%)   |
| Outro ES            | 8s         | 2/92 (2%)   |
| TTS EN              | 3s         | 1/92 (1%)   |
| Mix audio EN        | 8s         | 2/92 (2%)   |
| Subtitulos EN       | 15s        | 3/92 (3%)   |
| Outro EN            | 8s         | 2/92 (2%)   |
| **TOTAL estimado**  | **~416s (~7 min)** | 100% |

### Formato de salida

```
[abc12345] Esperando GPU lock...
[abc12345] GPU lock adquirido
[abc12345] Generando 3 imagenes (FLUX schnell, 768x1344)...
[abc12345] ⏱ FLUX imagenes: 58s (total: 58s) [███░░░░░░░░░░░░░░░░░] 16% ETA: ~358s
[abc12345]    Clip 1/3: 82s (1m22s, total: 2m20s)
[abc12345]    Clip 2/3: 79s (3m21s, total: 4m39s)
[abc12345]    Clip 3/3: 81s (5m42s, total: 6m20s)
[abc12345] ⏱ Wan2.1 animacion: 4m02s (total: 5m00s) [██████████████░░░░░░] 71% ETA: ~103s
[abc12345] ⏱ MusicGen: 42s (total: 5m42s) [████████████████░░░░] 81% ETA: ~58s
[abc12345] === Version ES ===
[abc12345] ⏱ TTS ES: 3s (total: 5m45s) [████████████████░░░░] 83% ETA: ~55s
...
[abc12345] ════ PIPELINE COMPLETO en 7m12s ════
[abc12345] Tiempos: FLUX imagenes: 58s | Wan2.1 animacion: 4m02s | ...
```

La barra usa caracteres Unicode: `█` (lleno) y `░` (vacio), ancho 20 caracteres. El porcentaje se calcula con pesos relativos (Wan2.1 tiene peso 50 porque domina el tiempo total). La ETA se calcula sumando las estimaciones de fases aun no completadas.

### Uso en codigo

```python
from pipeline.timer import PipelineTimer

timer = PipelineTimer(job_id="abc123")
print(f"Estimacion total: {timer.estimated_total()}")  # "6m56s"

timer.start_phase("FLUX imagenes")
# ... generar imagenes ...
timer.end_phase("FLUX imagenes")    # Imprime barra + ETA

timer.start_phase("Wan2.1 animacion")
timer.log_subphase("Clip 1/3: 82s")  # Log dentro de la fase
timer.end_phase("Wan2.1 animacion")

total_seconds = timer.finish()       # Resumen final
```

---

## Errores comunes y soluciones

### GPU / Memoria

| Error | Causa | Solucion |
|-------|-------|----------|
| `CUDA out of memory` durante Wan2.1 | FLUX no se descargo antes | Verificar que `_unload()` se llama entre FLUX y Wan2.1 |
| `SVM thrashing` / sistema lento | Se uso `enable_model_cpu_offload()` | Usar `pipe.to("cuda")` siempre. Nunca cpu_offload en UMA |
| `RuntimeError: No HIP GPUs available` | ROCm no detecta la GPU | Verificar `HSA_ENABLE_SDMA=0`, kernel >= 6.18.4, `rocminfo` |
| Wan2.1 extremadamente lento (>10 min/clip) | Math attention en vez de flash | Verificar `sdp_kernel(enable_flash=True, enable_math=False)` |
| `GPU lock timeout after 3600s` | Otro proceso tiene el lock | Verificar con `lsof output/.gpu_lock`, matar proceso zombie |

### FFmpeg / Compositing

| Error | Causa | Solucion |
|-------|-------|----------|
| `ffmpeg failed` en export frames | ffmpeg no instalado o version vieja | `apt install ffmpeg` (requiere >= 4.4) |
| Subtitulos no aparecen | libass no instalado | `apt install libass-dev`, recompilar ffmpeg si es necesario |
| `Montserrat` no encontrada | Fuente no instalada | `apt install fonts-montserrat` o copiar a `/usr/share/fonts/` |
| Audio desincronizado | Clips con fps distinto al esperado | Verificar que todos los clips son @16fps |
| Aspect ratio incorrecto | Imagen de entrada no es 9:16 | El compositor escala+recorta a 1080x1920, pero el resultado es mejor si la fuente ya es 9:16 |

### TTS

| Error | Causa | Solucion |
|-------|-------|----------|
| `ImportError: chatterbox` | Chatterbox no instalado | `pip install chatterbox-tts`; cae a Kokoro automaticamente |
| `ImportError: kokoro` | Ningun motor TTS instalado | Genera silencio como ultimo recurso (no recomendado) |
| Audio vacio o muy corto | Texto demasiado corto o caracteres raros | `TTSEngine._clean()` filtra caracteres; verificar texto de entrada |

### MusicGen

| Error | Causa | Solucion |
|-------|-------|----------|
| Musica muy corta | `max_new_tokens` insuficiente | Incrementar `duration_seconds` (formula: tokens = duration * 50) |
| OOM en MusicGen con `cuda` | GPU aun ocupada por Wan2.1 | Usar `MUSIC_DEVICE=cpu` (por defecto) o verificar unload |

### Checkpoint / Pipeline

| Error | Causa | Solucion |
|-------|-------|----------|
| Pipeline se reanuda pero clips corruptos | Proceso matado durante escritura | Borrar el clip incompleto; el checkpoint salta clips con size > 1000 bytes |
| `checkpoint.json` corrupto | Escritura parcial | Borrar `output/tmp/{job_id}/checkpoint.json` para reiniciar desde cero |
| Directorio tmp no se limpia | Pipeline fallo antes de copiar a pending | Borrar manualmente `output/tmp/{job_id}/` |
