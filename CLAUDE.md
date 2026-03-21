# CLAUDE.md — VideoBot "Finanzas Claras"

## Misión
Construir un bot autónomo que genera y publica vídeos de finanzas personales en YouTube Shorts.
Todo el contenido es 100% generado con IA local (sin copyright).
Corre 24/7 en un GMKtec EVO-X2 con Ubuntu 24.04 y AMD Ryzen AI MAX+ 395.

## Datos del canal
- Canal: "Finanzas Claras"
- Handle: @finanzasjpg
- Gmail: finanzasjpg@gmail.com
- Google Cloud Project: finanzas-oc-yt
- Credenciales OAuth: credentials/yt_finanzas.json
- Plataforma inicial: YouTube Shorts únicamente

## Documentos — leer EN ESTE ORDEN
1. `docs/01_setup.md` — instalación Ubuntu + ROCm + dependencias
2. `docs/02_models.md` — descarga e instalación de modelos IA
3. `docs/03_agent.md` — agente LLM orquestador (Ollama local)
4. `docs/04_pipeline.md` — pipeline completo de generación
5. `docs/05_publisher.md` — subida a YouTube
6. `docs/06_scheduler.md` — scheduler y punto de entrada

## Stack técnico
- OS: Ubuntu 24.04 LTS (x86_64)
- GPU: AMD Radeon 8060S (gfx1151) — ROCm 7.2 + TheRock nightlies nativo (sin HSA_OVERRIDE)
- PyTorch: 2.11+ desde TheRock gfx1151 nightlies (`rocm.nightlies.amd.com/v2/gfx1151/`)
- Generación vídeo: Wan2.1 I2V 14B via diffusers (imagen → vídeo) — pipe.to("cuda"), NO cpu_offload
- Generación imagen: FLUX.1 schnell
- Voz: Chatterbox TTS (fallback: Kokoro)
- Música: MusicGen small (Meta)
- Edición: ffmpeg (subtítulos ASS estilo TikTok Montserrat Bold, loudnorm + sidechain ducking)
- LLM: Ollama + Qwen 2.5 14B (local) con fallback a Claude API
- Scheduler: APScheduler
- DB: SQLite
- Ejecución: nativa con venv (sin Docker) — `./run.sh`

## Notas ROCm (Strix Halo / gfx1151)
- TheRock nightlies: gfx1151 nativo, NO necesita HSA_OVERRIDE_GFX_VERSION
- NUNCA usar enable_model_cpu_offload() — causa SVM thrashing en UMA
- Usar pipe.to("cuda") siempre — la memoria es unificada (128 GB)
- HSA_ENABLE_SDMA=0 es obligatorio en APU
- Al descargar un modelo: del pipe + gc.collect() + torch.cuda.empty_cache()
- Los modelos cargan secuencialmente (FLUX → unload → Wan2.1 → unload → MusicGen)
- Kernel: 6.18.4+ requerido (actualmente 6.19.6-zabbly+)
- TTM: pages_limit=32505856 (124 GB GTT)

## Ejecución
```bash
./run.sh                  # scheduler automático (generación nocturna + publicación)
./run.sh generate         # generar 1 vídeo (modo IA: FLUX + Ken Burns)
./run.sh generate-stock   # generar 1 vídeo (modo stock: Pexels/Pixabay)
./run.sh publish          # publicar siguiente pendiente
./run.sh run              # generar + publicar
```

## Modos de generación de vídeo
- **Modo IA** (`VIDEO_SOURCE=ai`): FLUX.1 genera imágenes → Ken Burns/Wan2.1 anima → ~30-50 min/vídeo
- **Modo Stock** (`VIDEO_SOURCE=stock`): Pexels/Pixabay descarga clips → ~30-60 seg/vídeo, 0% GPU
- Se puede cambiar en .env o usar `generate-stock` para un solo vídeo
- El modo stock necesita PEXELS_API_KEY y/o PIXABAY_API_KEY en .env

## Fases de construcción
- [x] Fase 1: Setup del sistema (Ubuntu + ROCm 7.2 + TheRock + Python)
- [ ] Fase 2: Descarga de modelos IA (FLUX.1-schnell pendiente)
- [x] Fase 3: Pipeline de generación (imagen → vídeo → voz → edición)
- [x] Fase 4: Agente LLM (Ollama + Qwen 2.5 14B)
- [x] Fase 5: Publisher YouTube
- [x] Fase 6: Scheduler + punto de entrada

## Reglas
1. Nunca hardcodear credenciales — siempre desde .env
2. Logging en cada paso — nunca crashear silenciosamente
3. Cada vídeo registrado en SQLite antes de subir
4. Si falla YouTube API → guardar vídeo en /output/pending/ y reintentar
5. Máximo 2 vídeos/día para evitar penalizaciones iniciales
6. Sin Docker — ejecución nativa con venv
