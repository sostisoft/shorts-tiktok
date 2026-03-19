# Pipeline 100% local de video short-form en AMD Ryzen AI MAX+ 395

**Sí es posible construir este pipeline completamente local en el GMKtec EVO-X2**, aunque ningún proyecto existente lo implementa de extremo a extremo — se requiere integración personalizada. La combinación de **64 GB de memoria unificada** (que permite correr modelos de 14B sin cuantización), **Wan2.1/2.2 vía Wan2GP** (con soporte explícito para gfx1151), **Chatterbox Multilingual** para TTS en 23 idiomas con clonación de voz, y **MusicGen/ACE-Step** para música de fondo, forma un stack completamente funcional sobre ROCm. El cuello de botella principal es la velocidad de generación de video: ~4-8 minutos por clip de 5 segundos con el modelo 1.3B, lo que sitúa un video de 30 segundos en **25-50 minutos de procesamiento total**. La arquitectura óptima es un script Python que orqueste: Ollama (Qwen 2.5 14B) → Chatterbox TTS → Wan2.1 vía Wan2GP → FFmpeg (compositing + subtítulos ASS + ducking de audio).

---

## A. Generación de video con IA: Wan2.1 funciona en gfx1151 con workarounds específicos

### Wan2.1/2.2 en ROCm

Wan2.1 y Wan2.2 corren en gfx1151 con configuración específica. El proyecto **Wan2GP** (deepbeepmeep/Wan2GP) es la vía recomendada: su documentación `docs/AMD-INSTALLATION.md` lista `gfx1151` como arquitectura soportada con un índice pip dedicado. Un usuario con gfx1151 (Radeon 8060S) reportó en GitHub (ROCm/TheRock Discussion #655) generar videos de 2 segundos/25 frames a ~35s/iteración usando ComfyUI con `Total VRAM 110457 MB, pytorch version: 2.7.0a0, AMD arch: gfx1151, ROCm version: (6, 5)`.

Las variables de entorno críticas para gfx1151 son:

- `HSA_ENABLE_SDMA=0` — previene artefactos de tablero de ajedrez durante el decode VAE en APUs
- `HSA_OVERRIDE_GFX_VERSION=11.5.1` — necesario con stacks ROCm más antiguos
- `PYTORCH_HIP_ALLOC_CONF="backend:native,expandable_segments:True,garbage_collection_threshold:0.9,max_split_size_mb:512"`
- Flag `--fp32-vae` en ComfyUI para evitar errores MIOpen en el VAE

Los errores de MIOpen (`miopenStatusNotImplemented`) son el problema más común. El workaround es usar `MIOPEN_FIND_MODE=FAST` o VAE tiling con tiles de 256×256.

| Modelo | Resolución | Duración | VRAM | Notas gfx1151 |
|--------|-----------|----------|------|----------------|
| **Wan2.1 T2V-1.3B** | 832×480 | ~5s | **8.19 GB** | ✅ Funciona cómodamente |
| **Wan2.1 T2V-14B** | 1280×720 | ~5s | ~28 GB bf16 / ~17 GB FP8 | ✅ Cabe en 64 GB sin offloading |
| **Wan2.2 14B** | 720p+ | 6s (181 frames@30fps) | ~33 GB bf16 / ~17 GB FP8 | ✅ Ventaja clave del hardware |
| **Wan2.2 TI2V-5B** | 720p | 5s | ~8 GB | ✅ Opción equilibrada nueva |

### Alternativas compatibles con ROCm

**LTX-Video** es la alternativa más sólida: AMD la demostró oficialmente en su documentación ROCm (rocm.docs.amd.com) usando ComfyUI en RX 7900 XTX. El modelo **2B genera a 1216×704 a 30fps** y está soportado nativamente en ComfyUI y en Wan2GP. Sin embargo, algunos usuarios reportan salida de baja calidad ("garbage") en configuraciones AMD específicas.

**HunyuanVideo** (Tencent) funciona en ROCm con el ComfyUI-HunyuanVideoWrapper de kijai. Confirmado en RX 6700XT y 7900 XTX. El DiT necesita ~33 GB bf16 o ~17 GB FP8 — cabe perfectamente en 64 GB unificados. Existe una guía comunitaria (AlphafromZion/hunyuan-video-lora-amd) probada en RX 9700 XT con ROCm 7.2.

**CogVideoX** debería funcionar vía diffusers estándar de PyTorch. El modelo 2B necesita solo ~7-8 GB y genera clips de 6 segundos a 720×480. No hay reportes específicos en gfx1151, pero la arquitectura es PyTorch puro sin kernels CUDA propietarios.

**AnimateDiff** funciona en ComfyUI con ROCm pero consume significativamente más VRAM que en NVIDIA: un usuario reportó 16.3 GB para 512×512 vs 5.6 GB en NVIDIA equivalente. Genera clips cortos de 16-32 frames a 512×512, resolución insuficiente para producción.

### PyTorch wheels para gfx1151

Las wheels oficiales estables de PyTorch **no incluyen gfx1151**. Hay tres fuentes funcionales:

```bash
# 1. AMD Nightlies (TheRock) — RECOMENDADO
pip install --pre torch torchaudio torchvision --index-url https://rocm.nightlies.amd.com/v2/gfx1151/

# 2. AMD Pre-releases
pip install --pre torch --index-url https://rocm.prereleases.amd.com/whl/gfx1151/

# 3. Comunidad scottt/rocm-TheRock (releases estables para gfx1151)
# v6.5.0rc-pytorch-gfx110x: multi-arch wheel gfx1100-gfx1151-gfx1201
# "mainly tested and known to run fast on the Strix Halo (gfx1151)"
```

ROCm 7.2 introduce el target ISA `gfx11-generic`, permitiendo que software compilado para RDNA 3 corra en gfx1151 sin builds específicos. El rendimiento medido es ~36.9 TFLOPS BF16 (~62% del teórico de 59.4 TFLOPS) con un ancho de banda de memoria de **~212 GB/s** — significativamente menor que GPUs discretas (~1000 GB/s en RTX 4090), por lo que la inferencia será ~3-5× más lenta por paso, pero la capacidad de memoria es incomparablemente superior.

### ComfyUI en gfx1151

ComfyUI funciona con soluciones Docker específicas para gfx1151. **IgnatBeresnev/comfyui-gfx1151** es un proyecto Docker probado el 25 de febrero de 2026 en AMD Ryzen AI MAX+ 395, usando la imagen `rocm/pytorch` con Ubuntu 24.04, ROCm 7.2, Python 3.12 y PyTorch 2.9.1. Los flags de lanzamiento recomendados:

```bash
python main.py --listen 0.0.0.0 --fp32-vae --fast --disable-cuda-malloc \
  --normalvram --cache-classic --mmap-torch-files \
  --use-split-cross-attention --disable-smart-memory
```

Los workflows de video disponibles en ComfyUI incluyen kijai/ComfyUI-WanVideoWrapper (Wan2.1/2.2), ComfyUI-HunyuanVideoWrapper, nodos nativos de LTX-Video, y AnimateDiff. ComfyUI puede automatizarse vía su API REST, lo que permite integrarlo en el pipeline Python.

---

## B. TTS multiidioma: Chatterbox Multilingual domina, Kokoro para velocidad en inglés

### Chatterbox Multilingual — la opción principal

**Chatterbox** (Resemble AI) es el motor TTS local más completo para este pipeline. Con **11,000+ estrellas en GitHub**, licencia MIT, y **soporte explícito para ROCm** (incluye `requirements-rocm.txt`), ofrece tres variantes:

- **Chatterbox Original**: inglés, 0.5B parámetros, control de emoción, clonación zero-shot
- **Chatterbox Multilingual**: **23 idiomas** (incluyendo español e inglés), 0.5B parámetros, clonación zero-shot
- **Chatterbox Turbo**: 350M parámetros, **6× tiempo real**, tags paralingüísticos ([cough], [laugh])

Para un canal de finanzas, Chatterbox Multilingual permite clonar una voz profesional neutra a partir de **7-20 segundos de audio de referencia** y usarla consistentemente en todos los idiomas. El control de exageración emocional permite ajustar el tono hacia monotono/profesional. En tests ciegos, supera a ElevenLabs con **63.75% de preferencia** de usuarios.

No distingue explícitamente entre español LATAM y español España a nivel de modelo, pero al clonar una voz con acento específico (mexicano, argentino, castellano), la salida reproduce ese acento fielmente.

### Comparación de alternativas TTS

| Motor | Idiomas | Español | Clonación | Velocidad | ROCm | Licencia |
|-------|---------|---------|-----------|-----------|------|----------|
| **Chatterbox Multi** | 23 | ✅ (sin distinción LATAM/España) | ✅ Zero-shot 7-20s | 6× real-time (Turbo) | ✅ Explícito | MIT |
| **XTTS v2** (idiap fork) | 17 | ✅ (code "es", fine-tune para LATAM) | ✅ Zero-shot 3-6s | ~Real-time GPU | ✅ Confirmado | CPML |
| **Kokoro** | 9 | ⚠️ Thin (3 voces, calidad inferior) | ❌ | **210× real-time** | ✅ PyTorch/ONNX | Apache 2.0 |
| **F5-TTS** | EN/ZH + fine-tunes | ⚠️ Fine-tune comunitario temprano | ✅ Zero-shot 15s | RTF 0.15 | ✅ Probable | MIT |
| **Piper** | 50+ | ✅ MX, AR, CO, ES (10 voces España) | ❌ | Instantáneo CPU | N/A (CPU only) | GPL |
| **MeloTTS** | 6 | ✅ (1 speaker, sin LATAM/España) | ❌ | Real-time CPU | ✅ PyTorch | MIT |
| **Fish Speech S1.5** | 8+ | ✅ Tier 2 | ✅ Zero-shot 10s | 150ms latencia | ✅ Probable | CC-BY-NC-SA |

**Piper** destaca para prototipado rápido: corre en CPU puro a velocidad instantánea incluso en Raspberry Pi, tiene **voces dedicadas para español mexicano, argentino, colombiano y europeo** (10 modelos para España), y su formato ONNX ultra-ligero (~15-100 MB por voz) no compite por GPU con la generación de video. La calidad es inferior a los modelos neuronales pero aceptable para previsualizaciones.

### Estrategia TTS recomendada para el pipeline

1. **Inglés**: Kokoro TTS (velocidad extrema, calidad #1 en HuggingFace Arena) o Chatterbox Turbo (si se necesita voz clonada consistente)
2. **Español (LATAM/España)**: Chatterbox Multilingual con audio de referencia de un hablante del acento deseado
3. **Otros idiomas**: Chatterbox Multilingual (23 idiomas) o XTTS v2 (17 idiomas)
4. **Fallback CPU** (mientras GPU genera video): Kokoro ONNX para inglés, Piper para español

Esto permite que **TTS corra en CPU mientras Wan2.1 usa la GPU**, paralelizando el pipeline.

---

## C. Arquitectura del pipeline completo: de título a video listo para subir

### Ningún proyecto existente resuelve todo

**MoneyPrinterTurbo** (~50,000 estrellas, último release v1.2.6 mayo 2025, MIT) es lo más cercano pero **usa footage de stock de Pexels, no generación IA local**. Soporta Ollama para LLM local y Whisper para subtítulos, pero el video viene de internet. Un fork extendido (Asad-Ismail/MoneyPrinterTurbo-Extended) añade Chatterbox TTS local, pero sigue sin video IA.

**ShortGPT** (~6,200 estrellas) requiere API de OpenAI/Gemini + ElevenLabs + Pexels — imposible correrlo 100% local. Desarrollo esporádico desde 2023.

**Wan2GP** es el componente más valioso: soporta Wan2.1/2.2, HunyuanVideo, LTX-Video en AMD GPUs con optimización para VRAM bajo, incluye batch queuing, y tiene integración con Chatterbox TTS. Es activamente mantenido (commits de marzo 2026).

### Arquitectura recomendada

```
INPUT: título + descripción + idioma (es-LATAM / es-ES / en / fr / ...)
  │
  ▼
┌──────────────────────────────────────────────────┐
│ ETAPA 1: GENERACIÓN DE GUIÓN                     │
│ Ollama + Qwen 2.5 14B-Instruct (Q4_K_M)        │
│ → JSON: escenas[], narración[], prompts_visuales[]│
│ → Timing estimado por escena                      │
│ ~5-10 segundos en 64 GB unificados               │
└──────────────────────────────────────────────────┘
  │
  ▼ (paralelo: TTS en CPU + Video en GPU)
┌────────────────────────┐  ┌──────────────────────────┐
│ ETAPA 2a: TTS (CPU)    │  │ ETAPA 2b: VIDEO IA (GPU) │
│ Chatterbox Multilingual │  │ Wan2.1 1.3B vía Wan2GP   │
│ o Kokoro/Piper          │  │ o ComfyUI + WanWrapper   │
│ → .wav por escena       │  │ → clips 5s 480p por escena│
│ ~2-5 seg total          │  │ ~4-8 min por clip         │
└────────────────────────┘  └──────────────────────────┘
  │                            │
  ▼                            ▼
┌──────────────────────────────────────────────────┐
│ ETAPA 3: SUBTÍTULOS                              │
│ whisper-timestamped (GPU) o desde texto del guión │
│ → timestamps palabra por palabra                  │
│ → pysubs2 genera .ass con estilo TikTok           │
└──────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────┐
│ ETAPA 4: MÚSICA DE FONDO                         │
│ MusicGen medium (GPU) o ACE-Step 1.5             │
│ → 30s de música corporativa/profesional           │
│ o selección aleatoria de librería pre-curada      │
└──────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────┐
│ ETAPA 5: COMPOSITING FFmpeg                      │
│ → Concatenar clips video                          │
│ → Scale/pad a 1080×1920 (9:16)                   │
│ → Loudnorm voz a -14 LUFS                        │
│ → Sidechaincompress (ducking música bajo voz)     │
│ → Burn subtítulos .ass                            │
│ → Encode H.264 CRF 18, AAC 192k, 30fps           │
│ → movflags +faststart                             │
└──────────────────────────────────────────────────┘
  │
  ▼
OUTPUT: video_final_1080x1920.mp4 listo para subir
```

### LLM local para generación de guión

**Qwen 2.5 14B-Instruct** es la elección óptima: mejor multilingüe de su clase (español e inglés igualmente fuertes), excelente en output JSON estructurado (necesario para escenas y prompts), cabe en Q4_K_M en 64 GB, y tiene licencia Apache 2.0. Se ejecuta vía Ollama (`ollama run qwen2.5:14b`). El prompt debe generar un JSON con escenas, texto de narración por idioma, prompts visuales en inglés (Wan2.1 funciona mejor con prompts en inglés), y timing estimado.

### Orquestación

Un **script Python simple con subprocess** es la mejor opción para v1 — el pipeline es determinístico, no necesita agentes IA ni orquestación compleja. Para producción, migrar a **Prefect** (decoradores Python nativos, retries, monitoreo). n8n puede servir como capa de scheduling/triggering encima. Apache Airflow y LangChain son innecesariamente complejos para una sola máquina.

```python
# pipeline.py — estructura básica
import subprocess, json, os

def generate_video(title: str, description: str, language: str = "es"):
    # 1. Generar guión con Ollama
    script = call_ollama(title, description, language)

    # 2. Paralelizar: TTS (CPU) + Video (GPU)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        tts_future = executor.submit(generate_tts, script["scenes"], language)
        video_future = executor.submit(generate_video_clips, script["visual_prompts"])

    audio_files = tts_future.result()
    video_clips = video_future.result()

    # 3. Generar subtítulos desde texto del guión
    ass_file = generate_ass_subtitles(script["scenes"], audio_files)

    # 4. Música (pre-generada o MusicGen)
    music_file = select_or_generate_music(script.get("mood", "corporate"))

    # 5. Compositing FFmpeg
    output = ffmpeg_composite(video_clips, audio_files, music_file, ass_file)
    return output
```

---

## D. Subtítulos estilo TikTok: Whisper funciona en ROCm, ASS para animación

### Whisper en gfx1151

OpenAI Whisper funciona en ROCm vía PyTorch. El proyecto `whisper-rocm` (davidguttman/whisper-rocm) logró **9× real-time con large-v3** en AMD Radeon 8060S (gfx1151) usando CTranslate2 compilado con HIP — **2× más rápido que whisper.cpp en el mismo hardware**. Para este pipeline, la opción más simple es usar HuggingFace Transformers con `return_timestamps="word"`:

```python
from transformers import pipeline
pipe = pipeline("automatic-speech-recognition",
                model="openai/whisper-large-v3",
                chunk_length_s=30, device="cuda",
                return_timestamps="word")
result = pipe("voiceover.wav")
# result["chunks"] contiene timestamps por palabra
```

Sin embargo, como el texto del guión ya existe (lo generó el LLM), **no es necesario transcribir**: se pueden generar los timestamps directamente alineando el texto con el audio TTS usando forced alignment, o simplemente distribuyendo las palabras uniformemente según la duración del audio de cada escena.

### Subtítulos palabra por palabra estilo TikTok

El estilo más popular muestra **1-3 palabras a la vez**, resaltando la palabra activa en un color diferente (amarillo o cian sobre blanco). La implementación usa **pysubs2** para generar archivos ASS con formato:

```python
import pysubs2
from pysubs2 import SSAFile, SSAEvent, SSAStyle, make_time, Color

subs = SSAFile()
subs.styles["Default"] = SSAStyle(
    fontname="Montserrat", fontsize=72,
    primarycolor=Color(255, 255, 255),  # Blanco
    outlinecolor=Color(0, 0, 0),         # Outline negro
    bold=True, outline=4, shadow=0,
    alignment=5, marginv=400             # Centro-inferior
)
subs.styles["Highlight"] = SSAStyle(
    fontname="Montserrat", fontsize=80,
    primarycolor=Color(0, 255, 255),     # Cian/amarillo
    outlinecolor=Color(0, 0, 0),
    bold=True, outline=4, alignment=5, marginv=400
)

for word in word_timestamps:
    event = SSAEvent(
        start=make_time(s=word["start"]),
        end=make_time(s=word["end"]),
        style="Highlight",
        text=word["text"].strip()
    )
    subs.append(event)
subs.save("subtitles.ass")
```

Fuentes populares: **Montserrat Bold, Bebas Neue, Poppins Bold**. Efectos: scale-up al aparecer (`\fscx120\fscy120`), cambio de color en palabra activa, outline grueso de 3-5px. FFmpeg quema el .ass con `ass=subtitles.ass` en el filtro de video.

---

## E. Música de fondo: MusicGen confirmado en ROCm, ACE-Step es la sorpresa

**MusicGen** (Meta AudioCraft) está **confirmado funcionando en ROCm** por el blog oficial de AMD. Se instala vía HuggingFace Transformers y genera audio a 32kHz. Con 64 GB de memoria unificada, incluso el modelo **large (3.3B, ~16 GB VRAM)** corre cómodamente. Para contenido financiero:

```python
from transformers import AutoProcessor, MusicgenForConditionalGeneration
processor = AutoProcessor.from_pretrained("facebook/musicgen-medium")
model = MusicgenForConditionalGeneration.from_pretrained(
    "facebook/musicgen-medium").to("cuda")
inputs = processor(
    text=["corporate ambient background, subtle piano, professional atmosphere"],
    padding=True, return_tensors="pt").to("cuda")
audio = model.generate(**inputs, max_new_tokens=1024)  # ~20s a 32kHz
```

**ACE-Step v1.5** es una alternativa superior: AMD la documentó oficialmente corriendo en la plataforma Ryzen AI MAX+ con **1.8× real-time** (genera más rápido que la reproducción). Corre en ComfyUI con ROCm, soporta letras, estilos variados y tags descriptivos. Es open-source en GitHub (ace-step/ACE-Step).

La estrategia óptima es **pre-generar una librería de 20-30 tracks** con MusicGen/ACE-Step categorizados por mood (corporativo, motivacional, noticiero, calmo) y seleccionar aleatoriamente para cada video. Esto evita regenerar música en cada ejecución del pipeline.

---

## F. Compositing FFmpeg: el comando completo para 9:16

El comando FFmpeg que combina todo — video IA + voz + música con ducking + subtítulos quemados — en un solo paso:

```bash
ffmpeg -i video_concat.mp4 -i voiceover.wav -i bgmusic.wav \
  -filter_complex "
    [1:a]loudnorm=I=-14:TP=-1.5:LRA=11[voice];
    [2:a]volume=0.15[music_quiet];
    [voice]asplit=2[sc][voice_out];
    [music_quiet][sc]sidechaincompress=threshold=0.02:ratio=6:attack=200:release=1000[music_ducked];
    [voice_out][music_ducked]amix=inputs=2:duration=first:dropout_transition=2[audio_mix];
    [audio_mix]loudnorm=I=-14:TP=-1.5:LRA=11[audio_final];
    [0:v]scale=1080:1920:force_original_aspect_ratio=decrease,
         pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,
         ass=subtitles.ass[v]
  " \
  -map "[v]" -map "[audio_final]" \
  -c:v libx264 -preset medium -crf 18 -profile:v high -level 4.1 \
  -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart -shortest \
  output_final.mp4
```

La cadena de filtros hace: loudnorm de voz a **-14 LUFS** → reduce volumen de música a 15% → sidechaincompress duckea la música cuando hay voz (ratio 6:1) → mezcla → loudnorm final → scale/pad a 1080×1920 → quema subtítulos ASS. Los settings de encoding (H.264 High Profile, CRF 18, 30fps, AAC 192k, `faststart`) cumplen las especificaciones de TikTok, Reels y Shorts.

**MoviePy 2.x** sirve para prototipado rápido en Python pero es más lento que FFmpeg directo para compositing pesado. La recomendación es usar pysubs2 para generar el ASS y FFmpeg vía subprocess para el compositing final.

---

## G. Proyectos existentes y cómo aprovecharlos

| Proyecto | Estrellas | Último release | ¿100% local? | ¿Video IA local? | Utilidad para este pipeline |
|----------|-----------|----------------|---------------|-------------------|-----------------------------|
| **MoneyPrinterTurbo** | ~50K | v1.2.6 (May 2025) | Parcial (Pexels requiere internet) | ❌ Stock footage | Referencia para arquitectura, Whisper, FFmpeg |
| **Wan2GP** | Activo | Marzo 2026 | ✅ | ✅ Wan2.1/2.2, HunyuanVideo, LTX | **Componente central** para video IA en AMD |
| **comfyui-gfx1151** | Nuevo | Feb 2026 | ✅ | ✅ Via workflows | Docker listo para gfx1151 |
| **ShortGPT** | ~6.2K | 2023 (revamp 2025) | ❌ (APIs requeridas) | ❌ | Solo inspiración de arquitectura |
| **AutoShorts** | Menor | Activo | Parcial (Ollama sí) | ❌ | Node.js, difícil integrar con Python |
| **MoneyPrinterTurbo-Extended** | Fork | Activo | Más local (Chatterbox TTS) | ❌ | Fork con TTS local añadido |

### Cómo construirlo: la ruta más práctica

La ruta más eficiente no es modificar MoneyPrinterTurbo sino **construir un pipeline nuevo usando componentes probados**:

1. **Tomar Wan2GP** como motor de video (ya soporta AMD, batch processing, CLI)
2. **Integrar Chatterbox TTS** (Wan2GP ya tiene integración parcial con Chatterbox)
3. **Usar Ollama** para generación de guión (mismo enfoque que MoneyPrinterTurbo)
4. **FFmpeg** para compositing (copiar los filtros de MoneyPrinterTurbo como referencia)
5. **pysubs2 + whisper-timestamped** para subtítulos

El tiempo total estimado por video de 30 segundos (6 escenas de 5s): **~30-50 minutos** dominado por la generación de video. Con batch overnight (queue de Wan2GP), se pueden producir **25-40 videos en 24 horas** sin intervención manual.

---

## Conclusión: viable pero con expectativas realistas de velocidad

Este pipeline es técnicamente viable hoy en el GMKtec EVO-X2. La pieza más madura es el compositing (FFmpeg), seguida de TTS (Chatterbox) y LLM (Qwen vía Ollama). La pieza más experimental es la generación de video IA en gfx1151 — funciona pero requiere configuración cuidadosa de variables de entorno y manejo de errores MIOpen. La ventaja decisiva de los **64 GB de memoria unificada** es poder correr Wan2.1/2.2 14B sin cuantización ni offloading, algo imposible en GPUs discretas de consumo. La desventaja es el ancho de banda de memoria (~212 GB/s vs ~1000 GB/s en RTX 4090), que resulta en generación **3-5× más lenta por paso** pero con capacidad de manejar modelos y secuencias significativamente más grandes. Para un canal de finanzas multiidioma con producción batch, la combinación de generación nocturna automatizada y la capacidad de producir decenas de videos diarios sin costo de API convierte este setup en una propuesta económicamente sólida.
