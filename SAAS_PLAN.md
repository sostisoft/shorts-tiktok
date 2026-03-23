# ShortForge — SaaS de generación automática de YouTube Shorts

## Contexto del proyecto actual

Pipeline autónomo de generación de YouTube Shorts de finanzas en español. Monolito single-tenant, CLI-only, ~3500 líneas Python.

### Arquitectura actual (6 fases)

1. Script Generation → Qwen 2.5 14B (Ollama local) con fallback a Claude CLI
2. Image Generation → FLUX.1-schnell (diffusers, GPU local)
3. TTS → Edge TTS (gratis) con fallback ElevenLabs
4. Video Generation → Ken Burns (FFmpeg) o Wan2.1 I2V (GPU local)
5. Music → MusicGen (CPU) o tracks royalty-free
6. Compositing → FFmpeg (H.264, ASS subtítulos estilo TikTok, 1080x1920)

### Stack actual

- Python 3.12, APScheduler, SQLAlchemy + SQLite, Flask + SocketIO (webui puerto 5050)
- Publishers: YouTube OAuth2 (funcional), TikTok/Instagram (stubs listos)
- Checkpointing por job en `output/jobs/{job_id}/checkpoint.json`
- Config via `.env` (VIDEO_SOURCE, VIDEO_ENGINE, TTS_ENGINE)

### Archivos clave

| Archivo | Líneas | Propósito |
|---|---|---|
| `main.py` | 162 | Entry point + scheduler |
| `scheduler/runner.py` | 586 | Orquestación 6 fases |
| `scheduler/checkpoint.py` | ~200 | Estado de jobs |
| `agents/script_agent.py` | 155 | Generación de guiones LLM |
| `agents/llm_client.py` | 106 | Claude CLI + Ollama |
| `pipeline/image_gen.py` | 156 | FLUX Schnell imágenes |
| `pipeline/video_gen.py` | ~200 | Wan2.1 I2V video |
| `pipeline/kenburns.py` | 89 | Ken Burns FFmpeg |
| `pipeline/tts.py` | ~200 | Edge TTS + ElevenLabs |
| `pipeline/music_gen.py` | 80 | MusicGen + tracks fallback |
| `pipeline/composer.py` | ~200 | FFmpeg compositing final |
| `pipeline/stock_video.py` | ~300 | Pexels/Pixabay stock footage |
| `db/models.py` | 74 | Video ORM SQLAlchemy |
| `publishers/youtube_publisher.py` | 141 | YouTube Data API v3 |
| `publishers/tiktok.py` | ~80 | TikTok API (stub) |
| `publishers/instagram.py` | ~100 | Instagram API (stub) |
| `webui/app.py` | 27.8KB | Flask dashboard + WebSocket logs |

---

## Arquitectura SaaS: VPS + APIs externas

Todo corre en un VPS. Sin GPU propia. Las fases de generación se ejecutan vía APIs externas.

### Topología

```
┌────────────────────────────────────┐
│  VPS ($10-20/mo)                   │
│                                    │
│  ▸ FastAPI (API pública)           │
│  ▸ PostgreSQL                      │
│  ▸ Redis (broker Celery + cache)   │
│  ▸ Celery Worker (orquesta APIs)   │
│  ▸ FFmpeg (compositing local)      │
│  ▸ Next.js Dashboard               │
│  ▸ Nginx + SSL + dominio           │
│  ▸ S3/MinIO (video storage)        │
│                                    │
└──────────┬─────────────────────────┘
           │ Llama APIs externas
           ▼
┌────────────────────────────────────┐
│  APIs Externas                     │
│                                    │
│  ▸ Claude API → scripts/guiones    │
│  ▸ fal.ai → FLUX imágenes          │
│  ▸ Kling API → video I2V           │
│  ▸ Replicate → Wan2.1 / alternativas│
│  ▸ ElevenLabs → TTS premium        │
│  ▸ Edge TTS → TTS gratis           │
│  ▸ Pexels/Pixabay → stock footage  │
│                                    │
└────────────────────────────────────┘
```

### Coste por video (APIs externas)

| Servicio | Función | Coste aprox |
|---|---|---|
| Claude API (Haiku) | Script/guión | ~$0.01-0.03 |
| fal.ai (FLUX) | 4 imágenes | ~$0.04-0.12 |
| Kling API | 4 clips video I2V | ~$0.40-1.20 |
| Replicate (Wan2.1) | 4 clips alternativo | ~$0.60-2.00 |
| ElevenLabs | TTS premium | ~$0.01-0.05 |
| Edge TTS | TTS gratis | $0 |
| Pexels/Pixabay | Stock footage | $0 |
| FFmpeg (VPS local) | Compositing | $0 |

**Rango por video:** $0.50-3.00 (modo AI completo) / $0.05-0.20 (stock + Ken Burns + Edge TTS)

### Pipeline refactorizado: cada fase con Strategy pattern

```python
# Cada fase tiene una interfaz común con múltiples providers
class ImageProvider(Protocol):
    async def generate(self, prompts: list[str], size: tuple) -> list[Path]: ...

class FalFluxProvider(ImageProvider): ...      # fal.ai FLUX API
class ReplicateFluxProvider(ImageProvider): ... # Replicate FLUX
class StockImageProvider(ImageProvider): ...    # Pexels/Pixabay

class VideoProvider(Protocol):
    async def generate(self, image: Path, motion_prompt: str) -> Path: ...

class KlingVideoProvider(VideoProvider): ...    # Kling API
class ReplicateWanProvider(VideoProvider): ...  # Replicate Wan2.1
class KenBurnsProvider(VideoProvider): ...      # FFmpeg local (gratis)

class TTSProvider(Protocol):
    async def generate(self, text: str, voice: str) -> Path: ...

class EdgeTTSProvider(TTSProvider): ...         # Gratis
class ElevenLabsProvider(TTSProvider): ...      # Premium

class ScriptProvider(Protocol):
    async def generate(self, topic: str, style: str) -> dict: ...

class ClaudeScriptProvider(ScriptProvider): ... # Claude API
class OllamaScriptProvider(ScriptProvider): ... # Si hay Ollama disponible
```

### Optimización de costes por plan

| Fase | Starter ($99) | Growth ($249) | Agency ($499) |
|---|---|---|---|
| Script | Claude Haiku | Claude Haiku | Claude Sonnet |
| Imágenes | Stock (Pexels) | fal.ai FLUX | fal.ai FLUX |
| Video | Ken Burns (FFmpeg) | Ken Burns | Kling API (AI) |
| TTS | Edge TTS (gratis) | Edge TTS | ElevenLabs |
| Música | Tracks royalty-free | Tracks | Tracks |
| **Coste/video** | **~$0.03** | **~$0.15** | **~$1.50** |
| **Videos/mes** | **15** | **30** | **90** |
| **Coste APIs/mes** | **~$0.45** | **~$4.50** | **~$135** |
| **Margen** | **~99%** | **~98%** | **~73%** |

---

## Modelo de negocio

### Target
- 10-30 clientes = $3k-$9k MRR
- Servicio boutique: onboarding manual, soporte directo
- Nicho inicial: creadores de contenido de finanzas en español

### Planes

| Plan | Precio | Videos/mes | Plataformas | Calidad video | TTS |
|---|---|---|---|---|---|
| Starter | $99/mo | 15 | YouTube | Stock + Ken Burns | Edge (gratis) |
| Growth | $249/mo | 30 | YouTube + TikTok | FLUX + Ken Burns | Edge (gratis) |
| Agency | $499/mo | 90 | YT + TikTok + IG | FLUX + Kling AI | ElevenLabs |

### Coste operativo mensual estimado

| Concepto | Coste |
|---|---|
| VPS (Hetzner/Contabo) | $10-20 |
| APIs externas (10 clientes mix) | $50-200 |
| Dominio + SSL | ~$1 |
| **Total** | **~$70-220/mo** |
| **Revenue (10 clientes mix)** | **~$2,500/mo** |
| **Margen neto** | **~90%+** |

---

## Qué construir (por fases)

### Fase 1 — API + Multi-tenancy + Worker (MVP vendible)

**Backend API (FastAPI):**

```
POST   /api/videos                  — crear job
GET    /api/videos                  — listar videos del tenant
GET    /api/videos/{id}             — estado del job + URL video
POST   /api/videos/{id}/publish     — publicar manualmente
DELETE /api/videos/{id}             — cancelar/eliminar
GET    /api/videos/{id}/preview     — preview antes de publicar
POST   /api/channels                — conectar canal YT/TikTok/IG
GET    /api/channels                — listar canales conectados
GET    /api/usage                   — métricas de uso del tenant
POST   /api/webhooks                — registrar webhook notificaciones
```

**Auth:**
- API keys por tenant (header `X-API-Key`)
- Onboarding manual (sin registro público por ahora)
- Rate limiting por plan

**Base de datos (PostgreSQL):**

```sql
-- Migrar de SQLite a PostgreSQL con Alembic
tenants        (id, name, email, api_key_hash, plan, created_at)
channels       (id, tenant_id, platform, credentials_encrypted, active)
videos         (id, tenant_id, channel_id, job_id, title, status, video_url, youtube_id, ...)
schedules      (id, tenant_id, channel_id, cron_expression, timezone, topic_pool, active)
usage_logs     (id, tenant_id, month, videos_generated, videos_published, api_cost)
webhook_endpoints (id, tenant_id, url, events, active)
```

**Worker (Celery + Redis):**
- Cada fase del pipeline como Celery task encadenable (chain)
- Strategy pattern: cada task elige provider según plan del tenant
- Retry con exponential backoff para APIs externas
- FFmpeg compositing corre en el VPS (no necesita GPU)
- Callback de completion → webhook al cliente + actualizar DB

**Storage:**
- Videos generados → S3 o MinIO en el VPS
- Presigned URLs para que el cliente descargue/previsualice
- Limpieza automática de videos > 90 días

**Docker Compose (VPS):**

```yaml
services:
  api:
    image: shortforge-api
    ports: ["8000:8000"]
    depends_on: [db, redis]

  db:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine

  worker:
    image: shortforge-worker
    depends_on: [redis]
    # FFmpeg instalado en la imagen

  nginx:
    image: nginx
    ports: ["80:80", "443:443"]

  minio:
    image: minio/minio
    ports: ["9000:9000"]

volumes:
  pgdata:
```

### Fase 2 — Dashboard web

- Next.js + Tailwind
- Login por tenant (API key o magic link)
- **Dashboard cliente:**
  - Grid de videos con thumbnails y estado
  - Estado de cada job (6 fases con progreso)
  - Calendario de publicación (drag & drop)
  - Conectar canales (YouTube OAuth, TikTok, Instagram)
  - Config: topics, estilo, idioma, timezone, schedule
  - Uso del mes vs límite del plan
- **Panel admin:**
  - Listado de tenants y uso
  - Cola de jobs en tiempo real
  - Costes de APIs por tenant
  - Métricas globales

### Fase 3 — Funcionalidades SaaS completas

- Multi-plataforma: activar TikTok + Instagram (stubs ya existen)
- Templates de video (documental, energético, educativo, listicle, storytelling)
- Trend intelligence: sugerir topics basados en tendencias
- Analytics: YouTube Analytics API → views, CTR, retention por video
- A/B testing: 2 versiones del mismo topic, medir rendimiento
- Scheduling flexible por timezone
- Billing: Stripe subscription + metering por videos generados
- Onboarding self-service (registro público + trial de 3 videos)

---

## Instrucciones de ejecución

1. Usa `/plan` para crear el plan detallado ANTES de tocar código
2. Empieza por Fase 1 (API + multi-tenancy + worker)
3. **NO borres funcionalidad existente** — el bot actual (@finanzasjpg) debe seguir funcionando
4. Implementa Strategy pattern para cada fase del pipeline (local vs API provider)
5. Mantén compatibilidad con `.env` actual (añadir nuevas vars, no romper existentes)
6. Tests para endpoints y lógica de routing de providers
7. Docker Compose para el stack VPS completo
8. El compositing (FFmpeg) siempre corre en el VPS — no necesita GPU
9. Usa Alembic para migraciones de PostgreSQL
10. Secrets (API keys de providers, credenciales OAuth) en variables de entorno, nunca en código
