# 02 - Modelos IA del Pipeline VideoBot

> Hardware: GMKtec EVO-X2 | AMD Ryzen AI MAX+ 395 | 128 GB RAM unificada | ROCm 7.2 | Ubuntu 24.04

Este documento describe todos los modelos de IA usados por el pipeline de VideoBot "Finanzas Claras",
con rutas reales, tamanios en disco, consumo de RAM GPU y comandos de descarga/verificacion.

**Principio clave**: Los modelos se cargan **secuencialmente** (uno a la vez) con `pipe.to("cuda")`
y se descargan con `del pipe + gc.collect() + torch.cuda.empty_cache()`. NUNCA usar `enable_model_cpu_offload()` en UMA.

---

## 1. FLUX.1-schnell --- Generacion de imagenes

| Campo | Valor |
|---|---|
| **Modelo** | `black-forest-labs/FLUX.1-schnell` |
| **Tipo** | Text-to-Image (diffusers `FluxPipeline`) |
| **Tamano en disco** | ~11 GB (cache HuggingFace) |
| **RAM GPU en uso** | ~16 GB (bf16, 1080x1920) |
| **Ruta cache** | `~/.cache/huggingface/hub/models--black-forest-labs--FLUX.1-schnell/` |
| **Ruta local (opcional)** | `models/flux-schnell/` (si se descarga localmente) |
| **Precision** | `torch.bfloat16` |
| **Parametros clave** | `steps=4`, `guidance_scale=0.0` (schnell no usa guidance) |
| **Resolucion** | 1080x1920 (vertical 9:16 para Shorts) |

### Descarga

```bash
# Opcion A: cache automatico de HuggingFace (se descarga al primer uso)
# El pipeline ya lo hace: FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell")

# Opcion B: descarga explicita con huggingface-hub
pip install huggingface-hub
huggingface-cli download black-forest-labs/FLUX.1-schnell --local-dir models/flux-schnell

# Opcion C: solo descargar al cache (sin copiar)
python -c "from huggingface_hub import snapshot_download; snapshot_download('black-forest-labs/FLUX.1-schnell')"
```

### Verificacion

```bash
# Verificar cache existe
du -sh ~/.cache/huggingface/hub/models--black-forest-labs--FLUX.1-schnell/
# Esperado: ~11 GB

# Verificar carga rapida
python -c "
from diffusers import FluxPipeline
import torch
pipe = FluxPipeline.from_pretrained('black-forest-labs/FLUX.1-schnell', torch_dtype=torch.bfloat16)
print('FLUX.1-schnell cargado OK')
del pipe
"
```

### Configuracion en codigo

Archivo: `pipeline/image_gen.py`

```python
FLUX_MODEL_ID = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell")
FLUX_LOCAL_PATH = Path(os.getenv("FLUX_LOCAL_PATH", "models/flux-schnell"))
```

Si `FLUX_LOCAL_PATH` existe, se usa esa ruta; si no, descarga desde HuggingFace Hub.

---

## 2. Wan2.1 I2V 14B --- Generacion de video

| Campo | Valor |
|---|---|
| **Modelo** | Wan2.1 Image-to-Video 14B (480p) |
| **Tipo** | Image-to-Video (diffusers `WanImageToVideoPipeline`) |
| **Tamano en disco** | ~84 GB total |
| **RAM GPU en uso** | ~35-45 GB (bf16, 480x832, 81 frames) |
| **Ruta local** | `models/wan21/` |
| **Precision** | `torch.bfloat16` |
| **Resolucion** | 480x832 (9:16 portrait, se upscalea con ffmpeg) |
| **FPS** | 16 fps, 81 frames = 5 segundos |
| **Parametros** | `guidance_scale=5.0`, `steps=10` |

### Componentes del modelo

```
models/wan21/
  transformer/      62 GB   (14 shards .safetensors)
  text_encoder/     22 GB   (UMT5EncoderModel, 5 shards)
  image_encoder/    1.2 GB  (CLIPVisionModelWithProjection)
  vae/              485 MB  (diffusion_pytorch_model.safetensors)
  tokenizer/        21 MB
  image_processor/  8 KB
  scheduler/        8 KB    (UniPCMultistepScheduler)
  model_index.json
```

### Descarga

```bash
# Descarga completa con huggingface-cli
huggingface-cli download Wan-AI/Wan2.1-I2V-14B-480P --local-dir models/wan21

# Alternativa con Python
python -c "
from huggingface_hub import snapshot_download
snapshot_download('Wan-AI/Wan2.1-I2V-14B-480P', local_dir='models/wan21')
"
```

### Verificacion

```bash
# Verificar tamano total
du -sh models/wan21/
# Esperado: ~84 GB

# Verificar todos los componentes
ls models/wan21/transformer/diffusion_pytorch_model-*.safetensors | wc -l
# Esperado: 14

# Verificar carga
python -c "
from diffusers import WanImageToVideoPipeline
import torch
pipe = WanImageToVideoPipeline.from_pretrained('models/wan21', torch_dtype=torch.bfloat16)
print('Wan2.1 I2V 14B cargado OK')
del pipe
"
```

### Configuracion en codigo

Archivo: `pipeline/video_gen.py`

```python
self.pipe = WanImageToVideoPipeline.from_pretrained("models/wan21", torch_dtype=dtype)
self.pipe.to("cuda")
self.pipe.enable_attention_slicing(slice_size="auto")  # reduce pico de memoria
self.pipe.vae.enable_tiling()                           # reduce pico en decode
```

### Optimizaciones activas

- **Attention slicing**: reduce pico de VRAM en self-attention
- **VAE tiling**: reduce pico durante decode de video
- **SDP kernel**: flash attention + memory-efficient attention (ROCm), math=False
- **Inferencia a 480x832**: mucho mas rapido que 1080x1920; se upscalea con ffmpeg

---

## 3. Qwen 2.5 14B --- LLM via Ollama

| Campo | Valor |
|---|---|
| **Modelo** | `qwen2.5:14b` |
| **Tipo** | LLM para guiones, prompts, metadata |
| **Tamano en disco** | ~9 GB (formato GGUF via Ollama) |
| **RAM en uso** | ~12 GB |
| **Gestion** | Ollama (servidor local) |
| **Rol** | Agente orquestador: genera guiones, prompts de imagen, titulos, descripciones |

### Descarga

```bash
# Descargar via Ollama
ollama pull qwen2.5:14b
```

### Verificacion

```bash
# Verificar que esta disponible
ollama list | grep qwen2.5:14b
# Esperado: qwen2.5:14b  7cdf5a0187d5  9.0 GB

# Test rapido
ollama run qwen2.5:14b "Responde solo 'OK' si funcionas"
```

### Nota

Tambien esta instalado `qwen2.5vl:72b-q4_K_M` (48 GB) como modelo de vision, pero NO se usa
en el pipeline de VideoBot. El modelo usado para generacion de guiones es `qwen2.5:14b`.

---

## 4. Chatterbox TTS --- Voz (primario)

| Campo | Valor |
|---|---|
| **Modelo** | Chatterbox TTS (Resemble AI) |
| **Tipo** | Text-to-Speech con clonacion de voz |
| **Tamano en disco** | ~2 GB (se descarga automaticamente al cache de HuggingFace) |
| **RAM en uso** | ~2-3 GB (corre en CPU) |
| **Dispositivo** | CPU (para no competir con GPU) |
| **Sample rate** | 24000 Hz |
| **Idiomas** | 23 idiomas incluyendo espanol |

### Descarga

Chatterbox se descarga automaticamente la primera vez que se invoca `ChatterboxTTS.from_pretrained()`.
Los pesos se guardan en el cache de HuggingFace (`~/.cache/huggingface/hub/`).

```bash
# Instalar paquete
pip install chatterbox-tts

# Pre-descargar el modelo (opcional)
python -c "
from chatterbox.tts import ChatterboxTTS
model = ChatterboxTTS.from_pretrained(device='cpu')
print('Chatterbox TTS descargado OK')
"
```

### Verificacion

```bash
# Verificar paquete instalado
pip show chatterbox-tts

# Test de generacion
python -c "
from chatterbox.tts import ChatterboxTTS
model = ChatterboxTTS.from_pretrained(device='cpu')
wav = model.generate('Hola, esto es una prueba de voz.')
print(f'Audio generado: {wav.shape}')
"
```

### Configuracion en codigo

Archivo: `pipeline/tts.py`

```python
self._model = ChatterboxTTS.from_pretrained(device="cpu")
wav = self._model.generate(text, audio_prompt_path=voice_sample, exaggeration=0.3, speed=1.0)
# exaggeration=0.3 = tono profesional neutro para finanzas
```

---

## 5. Kokoro TTS --- Voz (fallback)

| Campo | Valor |
|---|---|
| **Modelo** | Kokoro TTS |
| **Tipo** | Text-to-Speech (fallback si Chatterbox no esta instalado) |
| **Tamano en disco** | ~500 MB (se descarga automaticamente) |
| **RAM en uso** | ~1 GB (CPU) |
| **Dispositivo** | CPU |
| **Voz** | `ef_dora` (espanol) |
| **Sample rate** | 24000 Hz |

### Descarga

Kokoro se descarga automaticamente al primer uso via `KPipeline`.

```bash
# Instalar paquete
pip install kokoro

# Pre-descargar (opcional)
python -c "
from kokoro import KPipeline
pipeline = KPipeline(lang_code='e')
print('Kokoro descargado OK')
"
```

### Verificacion

```bash
pip show kokoro

python -c "
from kokoro import KPipeline
pipeline = KPipeline(lang_code='e')
gen = pipeline('Prueba de voz con Kokoro.', voice='ef_dora', speed=1.0)
for _, _, audio in gen:
    print(f'Audio shape: {audio.shape}')
    break
"
```

### Configuracion en codigo

Archivo: `pipeline/tts.py`

```python
# Se activa automaticamente si Chatterbox no esta instalado
from kokoro import KPipeline
pipeline = KPipeline(lang_code="e")  # e = espanol
generator = pipeline(text, voice="ef_dora", speed=1.0)
```

---

## 6. MusicGen small --- Musica de fondo

| Campo | Valor |
|---|---|
| **Modelo** | `facebook/musicgen-small` |
| **Tipo** | Text-to-Music (transformers `MusicgenForConditionalGeneration`) |
| **Tamano en disco** | ~2 GB (se descarga al cache de HuggingFace) |
| **RAM en uso** | ~2 GB (CPU) o ~1.5 GB (GPU) |
| **Dispositivo** | CPU por defecto (`MUSIC_DEVICE=cpu`) |
| **Sample rate** | 32000 Hz |
| **Duracion** | ~35 segundos por defecto |

### Descarga

MusicGen se descarga automaticamente la primera vez via `transformers`.

```bash
# Pre-descargar (opcional)
python -c "
from transformers import AutoProcessor, MusicgenForConditionalGeneration
processor = AutoProcessor.from_pretrained('facebook/musicgen-small')
model = MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-small')
print('MusicGen small descargado OK')
"
```

### Verificacion

```bash
# Verificar cache
du -sh ~/.cache/huggingface/hub/models--facebook--musicgen-small/ 2>/dev/null
# Esperado: ~2 GB (se crea tras primera descarga)

# Test de generacion
python -c "
from transformers import AutoProcessor, MusicgenForConditionalGeneration
import torch
proc = AutoProcessor.from_pretrained('facebook/musicgen-small')
model = MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-small')
inputs = proc(text=['upbeat corporate background music'], padding=True, return_tensors='pt')
with torch.no_grad():
    audio = model.generate(**inputs, max_new_tokens=256)
print(f'Audio generado: {audio.shape}')
"
```

### Configuracion en codigo

Archivo: `pipeline/music_gen.py`

```python
MUSIC_DEVICE = os.getenv("MUSIC_DEVICE", "cpu")
MUSIC_MODEL = os.getenv("MUSIC_MODEL", "facebook/musicgen-small")
```

Prompts tematicos de finanzas incluidos en el codigo para seleccion aleatoria.

---

## Tabla resumen

### Espacio en disco

| Modelo | Tamano | Ubicacion |
|---|---|---|
| FLUX.1-schnell | 11 GB | `~/.cache/huggingface/hub/models--black-forest-labs--FLUX.1-schnell/` |
| Wan2.1 I2V 14B | 84 GB | `models/wan21/` |
| Qwen 2.5 14B | 9 GB | Gestionado por Ollama (`~/.ollama/models/`) |
| Chatterbox TTS | ~2 GB | `~/.cache/huggingface/hub/` (auto-descarga) |
| Kokoro TTS | ~500 MB | `~/.cache/huggingface/hub/` (auto-descarga) |
| MusicGen small | ~2 GB | `~/.cache/huggingface/hub/` (auto-descarga) |
| **TOTAL** | **~108.5 GB** | |

### Consumo de RAM GPU (secuencial)

Los modelos se cargan y descargan uno por uno. Nunca hay mas de un modelo grande en memoria.

| Paso del pipeline | Modelo | RAM GPU | Dispositivo |
|---|---|---|---|
| 1. Guion / prompts | Qwen 2.5 14B | ~12 GB | Ollama (auto) |
| 2. Generar imagen | FLUX.1-schnell | ~16 GB | `cuda` (bf16) |
| 3. Animar video | Wan2.1 I2V 14B | ~35-45 GB | `cuda` (bf16) |
| 4. Voz en off | Chatterbox TTS | ~2-3 GB | `cpu` |
| 5. Musica de fondo | MusicGen small | ~2 GB | `cpu` |
| 6. Edicion final | ffmpeg | ~0 GB | CPU |

**Pico maximo de RAM GPU**: ~45 GB (durante generacion de video con Wan2.1)

**RAM total del sistema**: 128 GB unificada (GTT). Holgura suficiente para todos los modelos
incluso considerando el overhead del sistema operativo y buffers.

### Flujo de carga/descarga

```
Ollama (Qwen 2.5 14B)  -->  unload automatico por Ollama
FLUX.1-schnell          -->  _unload() tras generar imagenes
Wan2.1 I2V 14B          -->  unload() tras generar video
Chatterbox/Kokoro TTS   -->  solo CPU, no compite con GPU
MusicGen small          -->  _unload() tras generar musica, solo CPU
```

---

## Comandos de descarga rapida (todos los modelos)

```bash
# 1. Wan2.1 (84 GB) --- el mas grande, descargar primero
huggingface-cli download Wan-AI/Wan2.1-I2V-14B-480P --local-dir models/wan21

# 2. FLUX.1-schnell (11 GB)
python -c "from huggingface_hub import snapshot_download; snapshot_download('black-forest-labs/FLUX.1-schnell')"

# 3. Qwen 2.5 14B (9 GB)
ollama pull qwen2.5:14b

# 4. MusicGen small (2 GB) --- se descarga automaticamente al primer uso
python -c "from transformers import MusicgenForConditionalGeneration; MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-small')"

# 5. Chatterbox TTS (2 GB) --- se descarga automaticamente al primer uso
python -c "from chatterbox.tts import ChatterboxTTS; ChatterboxTTS.from_pretrained(device='cpu')"

# 6. Kokoro TTS (500 MB) --- solo si se quiere como fallback
pip install kokoro && python -c "from kokoro import KPipeline; KPipeline(lang_code='e')"
```
