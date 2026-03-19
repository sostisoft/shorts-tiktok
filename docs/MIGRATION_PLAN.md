# Plan de Migración: Pipeline 100% Local + Optimización ROCm

**Fecha**: 2026-03-19
**Estado actual**: Pipeline funcional con Claude API (sonnet-4-6) + Kokoro TTS + FLUX + Wan2.1 + MusicGen
**Objetivo**: Pipeline 100% local + ROCm optimizado para gfx1151 + logs en tiempo real con estimaciones

---

## Resumen de Cambios

| Componente | Actual | Nuevo | Impacto |
|-----------|--------|-------|---------|
| LLM (guión) | Claude API (sonnet-4-6) | Ollama + Qwen 2.5 14B | Elimina dependencia API |
| LLM (metadata) | Claude API (sonnet-4-6) | Ollama + Qwen 2.5 14B | Elimina dependencia API |
| ROCm GFX version | gfx1100 (INCORRECTO) | gfx1151 (nativo) | Fix rendimiento ~2-6x |
| CPU offload | enable_model_cpu_offload() | pipe.to("cuda") | Elimina SVM thrashing |
| Env vars ROCm | Mínimas | Completas para UMA/APU | Estabilidad + velocidad |
| Subtítulos | SRT básico (Arial 28pt) | ASS estilo TikTok (Montserrat Bold) | Calidad visual |
| Audio mix | amix simple | loudnorm + sidechain ducking | Audio profesional |
| Logs | Básicos con timers | Tiempo real + ETA + estimación total | UX |
| TTS | Kokoro (es: ef_dora, en: af_sarah) | Kokoro (se mantiene, funciona bien) | Sin cambio |
| Video gen | FLUX + Wan2.1 I2V | Se mantiene (funciona) | Sin cambio |
| Música | MusicGen small | Se mantiene (funciona) | Sin cambio |

---

## Estimación de Tiempo por Video (post-migración)

| Fase | Tiempo estimado | Notas |
|------|----------------|-------|
| 1. Guión (Ollama local) | ~5-15s | Qwen 2.5 14B Q4_K_M, ~30 tok/s |
| 2a. FLUX imágenes (×3) | ~30-90s | Sin cpu_offload → más rápido |
| 2b. Wan2.1 clips (×3) | ~120-360s | El cuello de botella principal |
| 3. Concat clips | ~2s | FFmpeg copy codec |
| 4. MusicGen | ~30-60s | GPU, 17s de audio |
| 5. TTS ES + EN | ~3-5s | Kokoro ONNX, CPU |
| 6. Mix audio (×2) | ~5-10s | FFmpeg loudnorm + ducking |
| 7. Subtítulos ASS (×2) | ~10-20s | FFmpeg burn ASS |
| 8. Outro (×2) | ~5-10s | FFmpeg drawtext |
| 9. Metadata (Ollama ×2) | ~10-20s | Qwen local |
| **TOTAL estimado** | **~4-10 min** | vs ~30-60 min actual (con offload roto) |

---

## Fases de Implementación

Cada fase deja el pipeline **funcional**. Si algo falla, el pipeline anterior sigue operativo.

### FASE 0: Backup y preparación
- [ ] Backup de ficheros actuales que se van a modificar
- [ ] Verificar que Ollama está instalado y Qwen 2.5 14B disponible
- [ ] Instalar fuente Montserrat Bold en el contenedor

### FASE 1: Optimización ROCm (Docker + env vars)
**Ficheros**: `Dockerfile`, `docker-compose.yml`
**Cambios**:
- `HSA_OVERRIDE_GFX_VERSION=11.0.0` → `11.5.1`
- `PYTORCH_ROCM_ARCH=gfx1100` → `gfx1151`
- Añadir: `HSA_ENABLE_SDMA=0`, `GPU_MAX_ALLOC_PERCENT=100`, `GPU_SINGLE_ALLOC_PERCENT=100`, `GPU_MAX_HEAP_SIZE=100`
- Añadir: `PYTORCH_HIP_ALLOC_CONF=backend:native,expandable_segments:True,garbage_collection_threshold:0.9`
- Quitar: `ROCBLAS_USE_HIPBLASLT=1` (no necesario con gfx1151 nativo)
- PyTorch: cambiar de `rocm6.2` a nightlies gfx1151 (o mantener rocm6.2 con el override correcto como paso intermedio)
**Riesgo**: Bajo — solo cambia variables de entorno
**Rollback**: Restaurar valores anteriores en docker-compose.yml

### FASE 2: Eliminar cpu_offload → pipe.to("cuda")
**Ficheros**: `pipeline/image_gen.py`, `pipeline/video_gen.py`
**Cambios**:
- `enable_model_cpu_offload()` → `pipe.to("cuda")`
- Añadir `gc.collect()` + `torch.cuda.empty_cache()` en `unload()`
- Mantener VAE tiling/slicing (sigue siendo útil)
**Riesgo**: Medio — si VRAM insuficiente, OOM. Pero 64GB unificados >> 24GB FLUX + 28GB Wan2.1 (cargan secuencialmente)
**Rollback**: Revertir a `enable_model_cpu_offload()`

### FASE 3: Claude API → Ollama (orchestrator + metadata)
**Ficheros**: `agents/orchestrator.py`, `agents/metadata_gen.py`, `docker-compose.yml`, `requirements.txt`
**Cambios**:
- Reemplazar `anthropic.Anthropic()` por llamadas HTTP a Ollama (`http://host.docker.internal:11434/api/generate` o red Docker)
- Mismo prompt system/user, solo cambia el transporte
- Modelo: `qwen2.5:14b` (ya instalado en Ollama)
- Parseo JSON: robustecer con regex fallback (modelos locales a veces añaden texto extra)
- Añadir `OLLAMA_HOST` como variable de entorno
- Quitar dependencia `anthropic` de requirements.txt (o mantener como opcional)
**Riesgo**: Medio — la calidad del JSON de Qwen puede ser inferior a Claude
**Rollback**: Flag `USE_LOCAL_LLM=true/false` para elegir entre Ollama y Claude API
**Test**: Generar 5 guiones y comparar calidad

### FASE 4: Subtítulos ASS estilo TikTok
**Ficheros**: `pipeline/editor.py`
**Cambios**:
- Reemplazar `burn_subtitles()` que genera SRT → nueva versión que genera ASS
- Fuente: Montserrat Bold (instalar en Dockerfile)
- 3 palabras por chunk, uppercase, outline 4px negro, color blanco/cian
- Alignment centrado, margin inferior ~400px (centro-bajo de pantalla)
- No necesita pysubs2 — se puede generar ASS directamente como string
**Riesgo**: Bajo — solo cambia formato de subtítulos
**Rollback**: Mantener función vieja como `burn_subtitles_srt()`

### FASE 5: Audio mix profesional (loudnorm + sidechain)
**Ficheros**: `pipeline/editor.py`
**Cambios**:
- Reemplazar `mix_audio()` con versión mejorada:
  - Voz: loudnorm a -14 LUFS
  - Música: volume 15% + sidechaincompress (ducking cuando hay voz)
  - Mix final: loudnorm -14 LUFS
**Riesgo**: Bajo — solo cambia filtro FFmpeg
**Rollback**: Mantener función vieja como `mix_audio_simple()`

### FASE 6: Logging mejorado con ETA y estimaciones
**Ficheros**: `pipeline/runner.py`
**Cambios**:
- Clase `PipelineTimer` que trackea cada fase con:
  - Tiempo transcurrido
  - ETA basado en promedio histórico (leer de DB `generation_time_s`)
  - Progreso porcentual estimado
  - Formato: `[job_id] [3/9] Wan2.1 clip 2/3: 45s (ETA: ~2m restantes) [████████░░] 65%`
- Guardar tiempos detallados por fase en checkpoint.json
- Al final: resumen con tiempo total y comparación con promedio
**Riesgo**: Nulo — solo mejora logging
**Rollback**: No necesario

### FASE 7: Actualizar CLAUDE.md y documentación
**Ficheros**: `CLAUDE.md`, `docs/`
**Cambios**:
- Actualizar stack técnico (quitar "Claude API", añadir "Ollama")
- Documentar nuevas variables de entorno ROCm
- Documentar estimaciones de tiempo por fase

---

## Orden de Ejecución

```
FASE 0 → FASE 1 → rebuild Docker → test rápido
       → FASE 2 → rebuild Docker → test generación completa
       → FASE 3 → rebuild Docker → test guión + metadata local
       → FASE 4 → rebuild Docker → test subtítulos
       → FASE 5 → rebuild Docker → test audio
       → FASE 6 → rebuild Docker → test logging
       → FASE 7 → documentación
```

Cada fase: modificar código → rebuild imagen → probar → confirmar que funciona → siguiente fase.

---

## Pre-requisitos

1. **Ollama corriendo** en el host con Qwen 2.5 14B:
   ```bash
   ollama list | grep qwen2.5
   # Si no está: ollama pull qwen2.5:14b
   ```

2. **Fuente Montserrat Bold** disponible:
   ```bash
   # Se instala en el Dockerfile
   apt-get install -y fonts-montserrat
   # o descarga manual a /usr/share/fonts/truetype/montserrat/
   ```

3. **Backup antes de empezar**:
   ```bash
   cp -r /home/gmktec/shorts /home/gmktec/shorts.backup.$(date +%Y%m%d)
   ```
