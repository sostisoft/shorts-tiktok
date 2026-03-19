# 06 — Scheduler y despliegue en producción

Punto de entrada del bot y configuración para funcionamiento autónomo 24/7.

---

## 1. Modos de ejecución

El script `run.sh` es el único punto de entrada. Configura las variables ROCm, activa el venv y lanza `main.py`.

| Comando | Qué hace |
|---|---|
| `./run.sh generate` | Genera **un** vídeo y lo guarda en `output/pending/` con estado `pending` en la DB |
| `./run.sh publish` | Publica el siguiente vídeo pendiente (FIFO por `created_at`) en YouTube |
| `./run.sh run` | Genera + publica inmediatamente (modo test completo) |
| `./run.sh` *(sin args)* | Arranca el **scheduler automático** — modo producción 24/7 |

### Modo manual

Útil para pruebas y depuración:

```bash
cd /home/gmktec/shorts
./run.sh generate       # probar generación sin subir nada
./run.sh publish        # forzar publicación del siguiente en cola
./run.sh run            # ciclo completo de test
```

### Modo scheduler (producción)

Sin argumentos, `main.py` arranca un `BlockingScheduler` de APScheduler que ejecuta los jobs automáticamente según el horario configurado. El proceso se queda en primer plano y no termina hasta recibir `SIGINT`/`SIGTERM`.

---

## 2. Horario del scheduler

Zona horaria: **Europe/Madrid** (configurada tanto en `main.py` como con `TZ=Europe/Madrid` en `run.sh`).

### Generación nocturna: 00:00 – 06:00

- Se lanza `night_generation_loop()` a las **00:00**.
- Genera vídeos en bucle hasta las 06:00 o hasta alcanzar `MAX_VIDEOS_PER_NIGHT` (por defecto **6**).
- Si una generación falla, espera 5 minutos antes de reintentar.
- `misfire_grace_time=3600` — si el bot arranca tarde (ej. tras reinicio), ejecuta el job si ha pasado menos de 1 hora desde la hora programada.

### Publicación: 09:00, 14:00, 19:00

Tres publicaciones diarias en los picos de consumo de la audiencia española de finanzas:

| Hora | Motivo |
|---|---|
| **09:00** | Apertura de mercados, hora del café, pico de consumo matutino |
| **14:00** | Pausa de la comida, segundo pico de actividad en redes |
| **19:00** | Fin de jornada laboral, máximo engagement en YouTube Shorts |

Cada publicación toma el vídeo más antiguo con estado `pending` de la DB (FIFO). Si no hay vídeos pendientes, no hace nada. `misfire_grace_time=1800` para cada job de publicación.

### Flujo diario típico

```
00:00  → night_generation_loop() genera hasta 6 vídeos
06:00  → fin del bucle nocturno (GPU libre)
09:00  → publish_only() → sube vídeo #1
14:00  → publish_only() → sube vídeo #2
19:00  → publish_only() → sube vídeo #3
00:00  → nuevo ciclo de generación
```

La variable `MAX_VIDEOS_PER_NIGHT` (`.env` o entorno) controla cuántos vídeos se generan por noche. Si se publican 3/día, generar 3-6 permite mantener un buffer de reserva.

---

## 3. Instalación como servicio systemd

El fichero `videobot.service` está en la raíz del proyecto.

### Instalación

```bash
# 1. Copiar el fichero de servicio (editar usuario y rutas primero)
sudo cp /home/gmktec/shorts/videobot.service /etc/systemd/system/videobot.service

# 2. Editar para ajustar usuario y rutas
sudo nano /etc/systemd/system/videobot.service
#   - Cambiar YOUR_USER → gmktec
#   - Cambiar /home/YOUR_USER/shorts-tiktok → /home/gmktec/shorts
#   - Verificar rutas del venv

# 3. Recargar systemd
sudo systemctl daemon-reload

# 4. Habilitar arranque automático
sudo systemctl enable videobot

# 5. Arrancar
sudo systemctl start videobot
```

### Contenido clave del servicio

```ini
[Unit]
Description=VideoBot Finanzas Claras
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=gmktec
WorkingDirectory=/home/gmktec/shorts
EnvironmentFile=/home/gmktec/shorts/.env
ExecStart=/home/gmktec/shorts/venv/bin/python main.py
Restart=on-failure
RestartSec=60
StandardOutput=append:/home/gmktec/shorts/logs/videobot.log
StandardError=append:/home/gmktec/shorts/logs/videobot_error.log

[Install]
WantedBy=multi-user.target
```

Variables de entorno ROCm imprescindibles (ya incluidas en el fichero de servicio):

- `HSA_ENABLE_SDMA=0` — obligatorio en APU
- `GPU_MAX_ALLOC_PERCENT=100` — permitir asignación completa de VRAM
- `PYTORCH_HIP_ALLOC_CONF=backend:native,expandable_segments:True,...`

> **Nota**: El servicio depende de `ollama.service`. Asegurarse de que Ollama está configurado como servicio también.

---

## 4. Operación diaria

### Ver logs en tiempo real

```bash
# Via journalctl (si corre como servicio systemd)
journalctl -fu videobot

# Via fichero de log directo
tail -f /home/gmktec/shorts/logs/videobot.log
```

### Consultar la cola de vídeos

```bash
# Últimos 10 vídeos (estado general)
sqlite3 /home/gmktec/shorts/db/videobot.db \
  "SELECT job_id, title, status FROM videos ORDER BY created_at DESC LIMIT 10"

# Solo pendientes
sqlite3 /home/gmktec/shorts/db/videobot.db \
  "SELECT job_id, title, created_at FROM videos WHERE status='pending' ORDER BY created_at"

# Conteo por estado
sqlite3 /home/gmktec/shorts/db/videobot.db \
  "SELECT status, COUNT(*) FROM videos GROUP BY status"

# Últimos publicados con enlace YouTube
sqlite3 /home/gmktec/shorts/db/videobot.db \
  "SELECT job_id, title, youtube_id, published_at FROM videos WHERE status='published' ORDER BY published_at DESC LIMIT 5"
```

### Control del servicio

```bash
sudo systemctl stop videobot       # parar el bot
sudo systemctl start videobot      # arrancar
sudo systemctl restart videobot    # reiniciar (ej. tras cambio de código)
sudo systemctl status videobot     # ver estado actual
```

### Forzar generación/publicación manual

```bash
cd /home/gmktec/shorts
./run.sh generate    # generar uno ahora (independiente del servicio)
./run.sh publish     # publicar el siguiente pendiente
```

> **Cuidado**: Si el servicio systemd está corriendo, no ejecutar `./run.sh` sin argumentos ya que habría dos schedulers compitiendo por la GPU.

---

## 5. Web UI — Dashboard de monitorización

**URL**: `http://192.168.1.100:5050`

### Arranque

```bash
cd /home/gmktec/shorts
./webui/run.sh
```

El script activa el venv, configura las rutas del proyecto y lanza `webui/app.py` (Flask + SocketIO en puerto 5050).

### Funcionalidades

- **Logs en tiempo real**: WebSocket que hace tail del fichero `logs/videobot.log` y emite cada línea nueva al navegador al instante.
- **Progreso de generación**: Barra de progreso que parsea los logs y detecta en qué paso del pipeline está (guión, FLUX, Wan2.1, TTS, MusicGen, compositing).
- **Estadísticas del sistema**: CPU, RAM, disco, temperatura CPU/NVMe, uso de GPU, VRAM, GTT, potencia GPU — todo leído de `/proc` y `/sys` en tiempo real.
- **Cola de vídeos**: Lista de todos los vídeos en la DB con su estado (pending/published/error).
- **Gestión de temas**: CRUD de `topic_ideas` — añadir, filtrar, cambiar estado, priorizar.
- **Generación bajo demanda**: Botón para encolar hasta 5 generaciones desde el navegador (llama a `./run.sh generate` en subprocess).

### API endpoints principales

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/status` | GET | Estado general: jobs activos, stats DB, métricas sistema |
| `/api/logs?lines=100` | GET | Últimas N líneas del log |
| `/api/videos` | GET | Lista de vídeos de la DB |
| `/api/generate` | POST | Encolar generación (`{"count": N}`, max 5) |
| `/api/queue` | GET | Estado de la cola de generación |
| `/api/topics` | GET/POST | Listar/añadir temas |

---

## 6. Variables de entorno

Todas las variables se definen en `/home/gmktec/shorts/.env`. El fichero se carga automáticamente con `python-dotenv` al arrancar `main.py`.

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `OLLAMA_URL` | URL del servidor Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modelo LLM para guiones | — |
| `ANTHROPIC_API_KEY` | API key de Claude (fallback) | — |
| `HF_TOKEN` | Token de Hugging Face para descargar modelos | — |
| `DB_PATH` | Ruta a la base de datos SQLite | `db/videobot.db` |
| `OUTPUT_DIR` | Directorio base de salida | `output` |
| `PENDING_DIR` | Directorio de vídeos pendientes | — |
| `MAX_VIDEOS_PER_NIGHT` | Máximo de vídeos por ciclo nocturno | `6` |

Las credenciales de YouTube OAuth están en `credentials/yt_finanzas.json` (ver `docs/05_publisher.md`).

> **Nunca** subir `.env` ni `credentials/` al repositorio.

---

## 7. Monitorización y salud

### Qué vigilar

| Señal | Problema | Acción |
|---|---|---|
| Log sin actividad a las 00:05 | Generación nocturna no arrancó | Comprobar `systemctl status videobot`, revisar logs de error |
| `status='error'` acumulándose en DB | Fallos en pipeline o en YouTube API | Revisar `error_message` en la DB y `logs/videobot_error.log` |
| GPU al 0% durante generación | Modelo no cargó en GPU | Verificar ROCm: `rocm-smi`, revisar que `HSA_ENABLE_SDMA=0` está configurado |
| RAM > 110 GB | Modelos no se descargan correctamente | Verificar que cada paso del pipeline hace `unload()` / `del pipe` + `torch.cuda.empty_cache()` |
| Disco > 90% | Vídeos temporales acumulados | Limpiar `output/tmp/` y vídeos antiguos de `output/published/` |
| `No hay vídeos pendientes` a las 09:00 | Generación nocturna falló o generó 0 | Revisar logs de la noche, ejecutar `./run.sh generate` manualmente |
| YouTube API quota exceeded | Se superó el límite diario | Esperar 24h, reducir `MAX_VIDEOS_PER_NIGHT` |

### Comandos de diagnóstico rápido

```bash
# Estado del servicio
sudo systemctl status videobot

# Últimas líneas de log con errores
grep -i error /home/gmktec/shorts/logs/videobot.log | tail -20

# Estado de la GPU
rocm-smi

# Espacio en disco
df -h /home/gmktec/shorts/output

# Vídeos pendientes en cola
sqlite3 /home/gmktec/shorts/db/videobot.db \
  "SELECT COUNT(*) as pendientes FROM videos WHERE status='pending'"

# Verificar que Ollama responde
curl -s http://localhost:11434/api/tags | python -m json.tool | head -5
```

### Logs

| Fichero | Contenido |
|---|---|
| `logs/videobot.log` | Log principal del pipeline (stdout del servicio) |
| `logs/videobot_error.log` | Errores y tracebacks (stderr del servicio) |

El log principal incluye timestamps y nivel (`INFO`, `WARNING`, `ERROR`) en cada línea. Los pasos del pipeline se identifican con prefijos `[1/6]` a `[6/6]`.

---

## Estructura de ficheros relacionados

```
shorts/
├── main.py                  # Punto de entrada + scheduler APScheduler
├── run.sh                   # Wrapper bash (ROCm env + venv + exec)
├── videobot.service         # Plantilla systemd
├── .env                     # Variables de entorno (no versionar)
├── scheduler/
│   └── runner.py            # Lógica: generate, publish, night_loop, run_job
├── db/
│   ├── models.py            # SQLAlchemy models (Video, VideoStatus)
│   └── videobot.db          # Base de datos SQLite
├── webui/
│   ├── app.py               # Flask + SocketIO dashboard
│   ├── run.sh               # Arranque de la web UI
│   ├── templates/           # HTML
│   └── static/              # CSS/JS
├── output/
│   ├── pending/             # Vídeos generados esperando publicación
│   ├── published/           # Vídeos ya subidos a YouTube
│   └── tmp/                 # Directorio temporal durante generación
└── logs/
    ├── videobot.log         # Log principal
    └── videobot_error.log   # Errores
```
