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
3. `docs/03_agent.md` — agente Claude orquestador
4. `docs/04_pipeline.md` — pipeline completo de generación
5. `docs/05_publisher.md` — subida a YouTube
6. `docs/06_scheduler.md` — scheduler y punto de entrada

## Stack técnico
- OS: Ubuntu 24.04 LTS (x86_64)
- GPU: AMD Radeon 890M (gfx1151) vía ROCm — HSA_OVERRIDE_GFX_VERSION=11.5.1
- Generación vídeo: Wan2.1 I2V (imagen → vídeo) — pipe.to("cuda"), NO cpu_offload
- Generación imagen: FLUX.1 schnell
- Voz: Kokoro TTS (español ef_dora, inglés af_sarah)
- Música: MusicGen small (Meta)
- Edición: ffmpeg (subtítulos ASS estilo TikTok, loudnorm + sidechain ducking)
- LLM: Ollama + Qwen 2.5 14B (local) con fallback a Claude API
- Scheduler: APScheduler
- DB: SQLite

## Notas ROCm (Strix Halo / gfx1151)
- NUNCA usar enable_model_cpu_offload() — causa SVM thrashing en UMA
- Usar pipe.to("cuda") siempre — la memoria es unificada
- HSA_ENABLE_SDMA=0 es obligatorio en APU
- Al descargar un modelo: del pipe + gc.collect() + torch.cuda.empty_cache()
- Los modelos cargan secuencialmente (FLUX → unload → Wan2.1 → unload → MusicGen)

## Fases de construcción
- [ ] Fase 1: Setup del sistema (Ubuntu + ROCm + Python)
- [ ] Fase 2: Descarga de modelos IA
- [ ] Fase 3: Pipeline de generación (imagen → vídeo → voz → edición)
- [ ] Fase 4: Agente Claude
- [ ] Fase 5: Publisher YouTube
- [ ] Fase 6: Scheduler + prueba end-to-end

## Reglas
1. Nunca hardcodear credenciales — siempre desde .env
2. Logging en cada paso — nunca crashear silenciosamente
3. Cada vídeo registrado en SQLite antes de subir
4. Si falla YouTube API → guardar vídeo en /output/pending/ y reintentar
5. Máximo 2 vídeos/día para evitar penalizaciones iniciales
