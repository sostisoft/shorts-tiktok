# Investigacion: Pipeline de Shorts con Stock Footage (sin IA para video)

**Fecha**: 2026-03-20
**Objetivo**: Reemplazar la generacion de imagenes/video con IA (FLUX.1 + Wan2.1) por stock footage gratuito sin copyright, usando herramientas locales para texto/edicion.

---

## ALERTA CRITICA: YouTube 2025-2026 y "Contenido Inautentico"

Antes de todo, hay que tener esto muy presente:

**YouTube actualizo sus reglas del Partner Program el 15 de julio de 2025** para atacar explicitamente el "contenido inautentico":
- Stock footage + voz IA + sin valor humano visible = **riesgo de demonetizacion**
- Compilaciones, clips reciclados, contenido "low effort" estan en el punto de mira
- No es que sea ilegal, pero YouTube puede **rechazar monetizacion** o limitarla

**Implicacion para Finanzas Claras**: El stock footage es legal y libre de Content ID (no tiene fingerprint como la musica), pero el canal necesita **aportar valor real** — datos actualizados, analisis original, graficos propios, narrador con personalidad — para no caer en la categoria de "inautentico". La clave es que el stock footage sea fondo/complemento visual, no el contenido principal.

**Monetizacion de Shorts**: Los creadores reciben el 45% de los ingresos publicitarios asignados a Shorts. Ingresos tipicos: $0.03-$0.10 por cada 1,000 vistas. Para ser elegible se necesitan 1,000 suscriptores + 10M vistas de Shorts en 90 dias (o 4,000 horas de watch time).

---

## A. APIs GRATUITAS DE VIDEO STOCK

### 1. Pexels API — LA MEJOR OPCION

| Campo | Detalle |
|-------|---------|
| **URL base** | `https://api.pexels.com/videos/search` |
| **Auth** | API Key en header `Authorization` |
| **Rate limit** | 200 requests/hora, 20,000/mes (free) |
| **Calidad** | HD, Full HD, 4K |
| **Licencia** | Pexels License (similar a CC0 pero custom) |
| **Atribucion** | NO requerida (pero apreciada) |
| **Uso comercial** | SI |
| **YouTube Shorts** | SI, sin problemas |
| **Content ID** | NO hay fingerprint — seguro |
| **Formato** | MP4 |
| **Busqueda** | Por keyword, orientacion, tamano, locale |
| **Filtro orientacion** | `orientation=portrait` para 9:16 |
| **Locale** | Soporta `es-ES` para busquedas en espanol |
| **Catalogo** | ~100,000+ videos |

```python
# Ejemplo: buscar videos verticales de finanzas
import requests

headers = {"Authorization": "TU_API_KEY"}
params = {
    "query": "finance money saving",
    "orientation": "portrait",  # 9:16 para Shorts
    "size": "medium",           # Full HD
    "per_page": 5,
    "locale": "es-ES"
}
r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)
videos = r.json()["videos"]

for v in videos:
    # Cada video tiene multiples resoluciones
    for f in v["video_files"]:
        if f["quality"] == "hd" and f["width"] < f["height"]:  # vertical
            print(f"Download: {f['link']}")
```

**Ventajas clave**:
- Filtro `orientation=portrait` nativo — perfecto para Shorts
- Sin rate limit agresivo para uso normal
- MoneyPrinterTurbo ya lo usa como fuente principal
- SDK Python disponible: `pexels-api-py`

**Gotchas**:
- No redistribuir los videos como stock footage (no revenderlos)
- Algunos videos son "patrocinados" — pueden tener marca visible
- La busqueda no siempre devuelve videos verticales aunque se pida `portrait`

---

### 2. Pixabay API — SEGUNDA MEJOR OPCION

| Campo | Detalle |
|-------|---------|
| **URL base** | `https://pixabay.com/api/videos/` |
| **Auth** | API Key como parametro `key=` |
| **Rate limit** | 100 requests/minuto (registrado), ilimitado real |
| **Calidad** | HD (1280), Full HD (1920), 4K (3840) |
| **Licencia** | Pixabay Content License (similar CC0) |
| **Atribucion** | NO requerida, pero deben mostrar "From Pixabay" al mostrar resultados de busqueda |
| **Uso comercial** | SI |
| **YouTube Shorts** | SI |
| **Content ID** | NO |
| **Formato** | MP4 |
| **Busqueda** | keyword, tipo, categoria, min_width/min_height |
| **Catalogo** | ~100,000+ videos, 5.6M+ imagenes+videos total |

```python
# Ejemplo Pixabay
params = {
    "key": "TU_API_KEY",
    "q": "finance+saving+money",
    "video_type": "film",  # film, animation, all
    "min_width": 1080,
    "min_height": 1920,     # Filtrar videos verticales
    "per_page": 5,
}
r = requests.get("https://pixabay.com/api/videos/", params=params)
hits = r.json()["hits"]

for hit in hits:
    # large = Full HD, medium = HD
    print(f"Download: {hit['videos']['large']['url']}")
    print(f"Duration: {hit['duration']}s")
```

**Ventajas**:
- Licencia mas permisiva que Pexels
- Tambien tiene MUSICA gratis (mismo API key, endpoint `/api/`)
- Rate limit generoso
- Tiene campo `duration` en la respuesta — util para seleccionar clips

**Gotchas**:
- No tiene filtro `orientation` nativo — hay que filtrar por min_width/min_height
- Obligatorio mostrar "Pixabay" cuando se muestran resultados (no aplica al video final)
- La calidad promedio es ligeramente inferior a Pexels

---

### 3. Coverr API — MEJOR PARA VIDEO VERTICAL

| Campo | Detalle |
|-------|---------|
| **URL base** | `https://api.coverr.co/` |
| **Auth** | `Authorization: Bearer API_KEY` header o `?api_key=KEY` |
| **Rate limit** | 50/hora (demo), 2,000/hora (produccion) |
| **Calidad** | HD, 4K |
| **Licencia** | Coverr License (libre para uso personal y comercial) |
| **Atribucion** | Debe mostrar logo Coverr clickable en la app (no en el video final) |
| **Uso comercial** | SI (no reventa) |
| **Formato** | MP4 |
| **Video vertical** | Campo `is_vertical` en la respuesta + coleccion dedicada de verticales |
| **Documentacion** | https://api.coverr.co/docs |

**Ventajas**: Videos de alta calidad cinematografica, campo `is_vertical` nativo, seccion dedicada de videos verticales para Shorts.
**Gotchas**: Hay que pedir API key por email, catalogo mas pequeno (~10K videos), no se puede hospedar los videos on-premise, requiere logo Coverr en la app/web.

---

### 4. Otras fuentes (sin API formal pero descargables)

| Fuente | Videos aprox | Licencia | API | Vertical | Notas |
|--------|-------------|----------|-----|----------|-------|
| **Mixkit.co** | ~45,000+ | Mixkit License (free, no atribucion) | NO | **1,300+ verticales** | Alta calidad, propiedad de Envato. Sin API pero gran libreria vertical |
| **Videvo.net** | ~15,000 free | Videvo Attribution License + CC0 parcial | NO | Pocos | Mezcla de licencias — verificar cada video |
| **Videezy** | ~10,000+ | Videezy License (atribucion requerida) | NO | Pocos | REQUIERE atribucion |
| **Life of Vids** | ~500 | CC0 | NO | No | Muy poca cantidad |
| **Dareful** | ~500 | CC0 | NO | No | Calidad decente pero pocas opciones |
| **Archive.org** | Millones | Public Domain | SI (API basica) | Mixto | Footage historico, calidad variable |
| **NASA** | Miles | Public Domain | NO formal | No | Solo tematica espacial |

**NOTA LEGAL IMPORTANTE**: Ni Pexels ni Pixabay usan licencia CC0 desde ~2019. Ambas cambiaron a licencias custom. Permiten uso comercial y YouTube, pero tienen restricciones (no reventa como stock, no ML training, no servicio de stock competidor). Ninguna ofrece indemnizacion por copyright.

**APIs que NO son gratuitas o NO existen**:
- **Videvo** — adquirida por Freepik en 2022, ahora API de pago (`api.freepik.com`)
- **Vecteezy** — API de pago desde $50/mes
- **Storyblocks** — solo enterprise, minimo $24K/ano
- **Mixkit** — excelentes videos gratis pero **NO tiene API**
- **Videezy** — **NO tiene API publica**

**Veredicto**: Para automatizacion, **Pexels** (primaria) + **Pixabay** (secundaria) + **Coverr** (complementaria) son las 3 unicas APIs gratuitas reales. El resto requiere scraping manual o descarga previa de libreria local. Usar las 3 maximiza variedad y distribuye rate limits.

---

## B. MUSICA SIN COPYRIGHT (con API)

### 1. Pixabay Music — LA MEJOR PARA AUTOMATIZAR

| Campo | Detalle |
|-------|---------|
| **URL** | Mismo API que Pixabay imagenes/videos |
| **Endpoint** | `https://pixabay.com/api/?type=music` (nota: no es endpoint separado, se filtra) |
| **Licencia** | Pixabay Content License — NO atribucion, SI comercial |
| **Formato** | MP3 |
| **Generos** | Ambient, Corporate, Lofi, Beats, Piano, etc. |
| **Content ID** | NO (clave para YouTube) |

**Ideal para fondo de Shorts financieros**: buscar "corporate ambient" o "soft piano background".

### 2. Freesound API

| Campo | Detalle |
|-------|---------|
| **URL** | `https://freesound.org/apiv2/` |
| **Auth** | API Key + OAuth2 para descargas |
| **Licencia** | Mixta (CC0, CC-BY, CC-BY-NC) — verificar cada sonido |
| **Uso comercial** | Depende de la licencia individual |
| **Catalogo** | 600,000+ sonidos |
| **Documentacion** | https://freesound.org/docs/api/ |

**Ventajas**: Enorme catalogo de efectos de sonido y loops musicales.
**Gotchas**: Muchos sonidos son CC-BY (requieren atribucion) o CC-BY-NC (no comercial). Hay que filtrar por `license=Creative Commons 0`.

### 3. Jamendo API — ALTERNATIVA CON API REAL

| Campo | Detalle |
|-------|---------|
| **URL** | `https://api.jamendo.com/v3.0/` |
| **Auth** | API Key como parametro `client_id=` |
| **Licencia** | Creative Commons (varias, por track) |
| **Catalogo** | 600,000+ tracks |
| **Uso comercial** | Depende de la licencia individual del track |
| **Documentacion** | https://developer.jamendo.com/v3.0/docs |

### 4. Otras fuentes de musica

| Fuente | Licencia | API | Content ID seguro | Notas |
|--------|----------|-----|--------------------|-------|
| **YouTube Audio Library** | YouTube-specific | NO oficial (JSON scrape no oficial existe) | **SI — la mas segura** | Pre-cleared por YouTube, cero riesgo Content ID |
| **Incompetech (Kevin MacLeod)** | CC-BY 3.0 | NO | **NO — alto riesgo** | Requiere atribucion, muchos temas en Content ID |
| **ccMixter** | CC | API basica (ccHost Query API) | Variable | Remixes y samples CC |
| **Unminus** | CC0-equivalente | NO | Probablemente seguro | Biblioteca pequena pero curada, sin atribucion |

**ADVERTENCIA CRITICA**: Pixabay Music **PUEDE disparar Content ID** en YouTube aunque sea "sin copyright". Varios creadores han reportado claims. Si se usa, descargar siempre el License Certificate y guardarlo para disputar claims.

### Estrategia recomendada para musica

**Opcion A (MAS SEGURA)**: YouTube Audio Library — descargar manualmente 20-30 tracks, cero riesgo.
**Opcion B (automatizada)**: Pixabay Music via web + Jamendo API — mayor variedad pero con riesgo menor de Content ID.
**Opcion C (ya implementada, CERO riesgo)**: MusicGen local — genera tracks unicos, imposible Content ID. RECOMENDADA para maximo control.
**Opcion D (pre-curada)**: Descargar 20-30 tracks de Pixabay Music + YouTube Audio Library, categorizarlos por mood, seleccionar aleatoriamente.

---

## C. SOFTWARE LOCAL PARA TEXTO/EDICION (sin IA)

### 1. FFmpeg + ASS Subtitles — YA IMPLEMENTADO, ES LA MEJOR OPCION

El pipeline actual ya usa FFmpeg con subtitulos ASS (pysubs2). Esto es exactamente lo correcto. No hay que cambiar nada aqui.

```bash
# El comando de compositing actual del pipeline ya es optimo:
ffmpeg -i video.mp4 -i voice.wav -i music.wav \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=decrease,
         pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,
         ass=subtitles.ass[v];
    ...
  " output.mp4
```

**Capacidades de FFmpeg drawtext/ASS que ya se pueden usar**:
- Texto con fade in/out: `\fad(200,200)` en ASS
- Texto escalado animado: `\fscx120\fscy120` con transiciones `\t()`
- Colores, sombras, outlines gruesos (estilo TikTok)
- Posicion flexible (centro, abajo, arriba)
- Fuentes custom (Montserrat Bold, Bebas Neue, Poppins)

**Animaciones avanzadas en ASS** (opcionales si se quiere mejorar):
```ass
; Palabra aparece con zoom-in
{\an5\pos(540,1200)\fscx50\fscy50\t(0,200,\fscx100\fscy100)}AHORRA
; Texto con karaoke highlight
{\an5\pos(540,1200)\k50}Hipoteca {\k80}fija {\k60}vs {\k80}variable
```

### 2. MoviePy 2.x (Python) — ALTERNATIVA PARA PROTOTIPADO

| Aspecto | Detalle |
|---------|---------|
| **Version actual** | 2.2.1 |
| **Vertical video** | SI (1080x1920) |
| **Texto animado** | SI (TextClip + CompositeVideoClip) |
| **Automatizable** | SI (100% Python) |
| **Rendimiento** | Mas lento que FFmpeg puro |
| **Subtitulos** | Limitado — mejor usar pysubs2 + FFmpeg |

```python
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

video = VideoFileClip("stock_clip.mp4").resized((1080, 1920))
txt = TextClip(text="AHORRA 300 EUR/MES", font="Montserrat-Bold",
               font_size=72, color="white", stroke_color="black", stroke_width=4)
txt = txt.with_position("center").with_duration(3).with_start(1)
final = CompositeVideoClip([video, txt])
final.write_videofile("output.mp4", fps=30)
```

**Veredicto**: Util para prototipar, pero FFmpeg+ASS es superior para produccion. No vale la pena cambiar.

### 3. Editly (Node.js) — ALTERNATIVA INTERESANTE

Editly genera videos desde un JSON declarativo. Soporta cualquier aspect ratio (9:16 para Shorts).

```json5
{
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "clips": [
    {
      "layers": [
        { "type": "video", "path": "stock_finance.mp4", "resizeMode": "cover" },
        { "type": "title", "text": "HIPOTECA FIJA VS VARIABLE",
          "position": "center", "fontPath": "Montserrat-Bold.ttf" }
      ]
    }
  ]
}
```

**Ventajas**: Declarativo, facil de generar JSON desde Python/LLM.
**Desventajas**: Ecosistema Node.js (no Python), depende de ffmpeg igualmente, menos control que ASS puro.

### 4. Remotion (React/JS) — POTENTE PERO OVERKILL

Remotion permite crear videos programaticamente con React. Extremadamente potente para animaciones complejas, graficos animados, y motion graphics. Pero:
- Requiere Node.js + React
- Rendering lento (headless Chrome)
- Overkill para el caso de uso actual
- Seria util si se quisieran graficos animados tipo "barras subiendo" o "tartas girando"

**Veredicto**: Guardarlo para el futuro si se quieren graficos animados de datos financieros. Para stock footage + texto, FFmpeg+ASS es suficiente.

---

## D. PROYECTOS OPEN SOURCE EXISTENTES (lo que ya esta hecho)

### 1. MoneyPrinterTurbo — EL REFERENTE

| Campo | Detalle |
|-------|---------|
| **GitHub** | harry0703/MoneyPrinterTurbo |
| **Stars** | ~50,000 |
| **Lenguaje** | Python |
| **Licencia** | MIT |
| **Video source** | Pexels API (stock footage) |
| **TTS** | Edge-TTS, Azure, OpenAI TTS |
| **LLM** | OpenAI, Gemini, Ollama (local) |
| **Subtitulos** | Whisper + ASS |
| **Musica** | Seleccion de libreria local |

**Lo que hace bien**:
- Pipeline completo: tema -> guion -> buscar videos -> TTS -> subtitulos -> compositing
- Usa Pexels para stock footage con busqueda semantica por keywords del guion
- Whisper para timestamps de subtitulos
- FFmpeg para compositing final
- Soporta Ollama para LLM local

**Lo que le falta**:
- TTS es cloud (Edge-TTS/Azure)
- No tiene Chatterbox ni Kokoro
- No optimizado para AMD/ROCm
- WebUI pesada (Streamlit)

**CONCLUSION**: Su modulo de busqueda de videos en Pexels es el codigo mas util para copiar/adaptar.

---

### 2. SaarD00/AI-Youtube-Shorts-Generator — PIPELINE FACELESS COMPLETO

| Campo | Detalle |
|-------|---------|
| **GitHub** | SaarD00/AI-Youtube-Shorts-Generator |
| **Lenguaje** | Python |
| **Video source** | Pexels (2 videos/escena, estilo A/B split) |
| **TTS** | Suno Bark (via Colab) |
| **LLM** | Gemini 2.0 Flash |

**Lo interesante**: Descarga 2 videos distintos por escena de Pexels y los alterna (split A/B), creando variedad visual. Usa transiciones xfade entre escenas. Buen ejemplo de como maximizar engagement con stock footage.

---

### 3. alamshafil/auto-shorts — PAQUETE PYTHON

| Campo | Detalle |
|-------|---------|
| **GitHub** | alamshafil/auto-shorts |
| **Lenguaje** | Python + Next.js (web UI) |
| **Video source** | Stock footage |
| **TTS** | Integrado |

Paquete Python instalable que genera shorts automaticamente. Tiene web UI con Next.js/Express.

---

### 4. marvinvr/auto-yt-shorts

Genera y procesa contenido de video basado en input del usuario. Maneja metadata, stock footage, voiceover y upload automatico.

---

### 5. short-video-maker — ARQUITECTURA MAS MODERNA

| Campo | Detalle |
|-------|---------|
| **GitHub** | gyoridavid/short-video-maker |
| **Stars** | ~1,000 |
| **Lenguaje** | TypeScript |
| **Video source** | Pexels API |
| **TTS** | Kokoro TTS (local) |
| **Subtitulos** | Whisper (local) |
| **Rendering** | Remotion (React) |
| **API** | MCP + REST API — integrable con n8n y agentes IA |
| **Docker** | SI |

**Lo interesante**: Arquitectura moderna con MCP (Model Context Protocol), permitiendo que agentes IA orquesten la generacion. Usa Kokoro TTS (el mismo que ya tenemos) y Remotion para rendering de alta calidad.

### 6. MoneyPrinterV2 — VERSION EXTENDIDA

| Campo | Detalle |
|-------|---------|
| **GitHub** | FujiwaraChoki/MoneyPrinterV2 |
| **Stars** | ~16,500 |
| **Lenguaje** | Python |
| **Extra** | Anade automatizacion de Twitter y marketing de afiliados |

### 7. RedditVideoMakerBot — PARA FORMATO REDDIT

| Campo | Detalle |
|-------|---------|
| **GitHub** | elebumm/RedditVideoMakerBot |
| **Stars** | ~8,350 |
| **Lenguaje** | Python |

Scrapes Reddit -> TTS -> overlay screenshots sobre gameplay -> subtitulos. El mas popular para Reddit-to-video.

### 8. Otros repositorios relevantes

| Proyecto | Stars | Que hace |
|----------|-------|----------|
| Binary-Bytes/Auto-YouTube-Shorts-Maker | Menor | Script simple para generar shorts |
| Alfinjohnson/Auto-YouTube | Menor | Generador + uploader automatico |
| Dark2C/Viral-Faceless-Shorts-Generator | ~42 | Google Trends driven, Docker, FFmpeg |
| neutraltone/awesome-stock-resources | 13K+ | Lista curada de recursos de stock gratuitos |

---

## E. PIPELINE PROPUESTO: Stock Footage para "Finanzas Claras"

### Arquitectura nueva (reemplazando FLUX.1 + Wan2.1)

```
INPUT: titulo + descripcion del tema financiero
  |
  v
+--------------------------------------------------+
| ETAPA 1: GENERACION DE GUION (sin cambios)       |
| Ollama + Qwen 2.5 14B                            |
| -> JSON: escenas[], narracion[], keywords[]       |
| -> Keywords de busqueda para stock footage        |
| ~5-10 segundos                                    |
+--------------------------------------------------+
  |
  v (paralelo)
+------------------------+  +---------------------------+
| ETAPA 2a: TTS (CPU)   |  | ETAPA 2b: STOCK VIDEO     |
| Chatterbox / Kokoro    |  | Pexels API + Pixabay API  |
| (sin cambios)          |  | -> Buscar por keywords     |
| -> .wav por escena     |  | -> Filtrar portrait/HD     |
| ~2-5 seg               |  | -> Descargar MP4           |
+------------------------+  | -> Cache local             |
  |                         | ~5-15 seg (download)       |
  |                         +---------------------------+
  |                            |
  v                            v
+--------------------------------------------------+
| ETAPA 3: SUBTITULOS (sin cambios)                |
| pysubs2 -> .ass estilo TikTok                    |
+--------------------------------------------------+
  |
  v
+--------------------------------------------------+
| ETAPA 4: MUSICA (opciones)                       |
| A) Pixabay Music API (download)                  |
| B) Libreria pre-curada local                     |
| C) MusicGen local (sin cambios)                  |
+--------------------------------------------------+
  |
  v
+--------------------------------------------------+
| ETAPA 5: COMPOSITING FFmpeg (sin cambios)        |
| -> Concatenar clips stock                         |
| -> Scale/pad a 1080x1920                         |
| -> Burn subtitulos ASS                           |
| -> Audio mix (voz + musica + ducking)            |
| -> H.264 CRF 18, 30fps                          |
+--------------------------------------------------+
  |
  v
OUTPUT: video_final_1080x1920.mp4

TIEMPO TOTAL ESTIMADO: ~30-60 SEGUNDOS (vs 30-50 MINUTOS con IA)
```

### Ventajas enormes del cambio:

| Metrica | Con IA (FLUX + Wan2.1) | Con Stock Footage |
|---------|------------------------|-------------------|
| **Tiempo por video** | 30-50 minutos | 30-60 segundos |
| **Uso GPU** | 100% durante generacion | 0% (solo CPU + red) |
| **Videos/dia** | 25-40 (batch nocturno) | **1,000+** (ilimitado) |
| **Calidad visual** | Variable (IA puede fallar) | Consistente (footage profesional) |
| **Costo** | Electricidad GPU | 0 (APIs gratuitas) |
| **Riesgo copyright** | 0 (generado) | ~0 (licencia libre) |
| **Dependencia internet** | No | SI (para buscar videos) |
| **Originalidad visual** | Alta (unico) | Baja (stock compartido) |

### Desventajas y mitigaciones:

1. **Videos repetidos**: Otros canales pueden usar los mismos clips de Pexels.
   - **Mitigacion**: Aplicar filtros de color, crop creativo, zoom lento, overlay de graficos.

2. **No hay videos especificos**: "cuota de autonomos en Espana" no tendra resultados exactos.
   - **Mitigacion**: Buscar keywords genericos ("freelancer", "taxes", "calculator", "office") y dejar que la narracion de el contexto.

3. **YouTube "inauthentic content"**:
   - **Mitigacion**: Anadir graficos propios (numeros, datos, comparativas), usar voz con personalidad, incluir intro/outro reconocible, variar la edicion.

4. **Necesita internet**: Para buscar y descargar videos.
   - **Mitigacion**: Cache local agresivo. Descargar 500-1000 videos de temas financieros una vez y usar como libreria offline.

---

## F. ESTRATEGIA DE CACHE/LIBRERIA LOCAL

### Pre-descarga por categorias financieras

```python
FINANCE_KEYWORDS = {
    "ahorro": ["saving money", "piggy bank", "coins jar", "wallet cash"],
    "hipoteca": ["house keys", "mortgage signing", "real estate", "apartment building"],
    "impuestos": ["tax forms", "calculator", "accountant office", "paperwork desk"],
    "inversion": ["stock market", "trading screen", "growth chart", "portfolio"],
    "jubilacion": ["retirement couple", "elderly happy", "pension planning", "golden years"],
    "autonomos": ["freelancer laptop", "home office", "self employed", "coworking"],
    "inflacion": ["price tags", "grocery shopping", "rising prices", "money burning"],
    "cripto": ["bitcoin", "cryptocurrency", "blockchain", "digital currency"],
    "presupuesto": ["budget planning", "spreadsheet", "calculator notebook", "financial planning"],
    "deuda": ["credit card", "debt papers", "bills pile", "loan document"],
    "genericos": ["business meeting", "city skyline", "modern office", "person thinking",
                   "typing laptop", "phone scrolling", "coins falling", "banknotes"]
}
```

### Esquema de cache

```
assets/
  stock-videos/
    index.json          # Metadata de todos los videos descargados
    ahorro/
      pexels_12345.mp4  # Video original de Pexels
      pexels_12345.json # Metadata (fuente, keywords, orientacion, duracion)
    hipoteca/
      ...
    genericos/
      ...
```

Esto permite:
1. **Modo online**: Buscar en API, descargar si no esta en cache, guardar en cache
2. **Modo offline**: Usar solo videos de la libreria local
3. **Modo hibrido**: Intentar API, fallback a cache local

---

## G. COMPARATIVA FINAL: Que cambiar y que mantener

| Componente | Actual | Propuesto | Cambio necesario |
|-----------|--------|-----------|------------------|
| **LLM (guion)** | Ollama + Qwen 2.5 14B | Sin cambios | Ninguno |
| **Imagenes** | FLUX.1 schnell | **ELIMINAR** — reemplazar por stock video | Nuevo modulo |
| **Video** | Wan2.1 I2V 14B | **ELIMINAR** — reemplazar por stock video | Nuevo modulo |
| **TTS** | Chatterbox / Kokoro | Sin cambios | Ninguno |
| **Musica** | MusicGen local | Opcion: Pixabay Music API o mantener | Opcional |
| **Subtitulos** | pysubs2 + ASS | Sin cambios | Ninguno |
| **Compositing** | FFmpeg | Sin cambios (adaptar concatenacion) | Menor |
| **Publicacion** | YouTube API | Sin cambios | Ninguno |

### Modulos nuevos a crear:

1. **`pipeline/stock_video.py`** — Buscar y descargar videos de Pexels/Pixabay
2. **`pipeline/video_cache.py`** — Gestion de cache local de videos stock
3. **`pipeline/stock_music.py`** — (Opcional) Buscar musica en Pixabay Music

### Modulos a eliminar/reducir:
1. **`generate_image.py`** — Ya no necesario
2. **`pipeline/image_gen.py`** — Ya no necesario
3. **Modelos FLUX.1 y Wan2.1** — Liberar ~50 GB de disco
4. **Dependencias**: diffusers, accelerate, safetensors (si no se usan para otra cosa)

---

## H. PROMPT DEL LLM PARA GENERAR KEYWORDS DE BUSQUEDA

El guion generado por Qwen necesita incluir keywords de busqueda para stock footage:

```json
{
  "title": "Hipoteca fija vs variable en 2026",
  "scenes": [
    {
      "scene_id": 1,
      "duration": 5,
      "narration": "Vas a comprar tu primera casa? La decision mas importante es el tipo de hipoteca.",
      "stock_keywords": ["couple signing mortgage", "house keys handover", "real estate office"],
      "text_overlay": "HIPOTECA FIJA VS VARIABLE",
      "mood": "intriguing"
    },
    {
      "scene_id": 2,
      "duration": 5,
      "narration": "La hipoteca fija te da una cuota que no cambia nunca. Pagas lo mismo el primer mes y el ultimo.",
      "stock_keywords": ["stable graph", "fixed rate", "calculator budget", "calm person"],
      "text_overlay": "FIJA = CUOTA ESTABLE",
      "mood": "reassuring"
    }
  ]
}
```

---

## I. REFERENCIAS Y FUENTES

### APIs
- Pexels API: https://www.pexels.com/api/documentation/
- Pixabay API: https://pixabay.com/api/docs/
- Coverr API: https://api.coverr.co/docs
- Freesound API: https://freesound.org/docs/api/

### Proyectos de referencia
- MoneyPrinterTurbo: https://github.com/harry0703/MoneyPrinterTurbo
- MoneyPrinterTurbo-Extended: https://github.com/Asad-Ismail/MoneyPrinterTurbo-Extended
- AI-Youtube-Shorts-Generator: https://github.com/SaarD00/AI-Youtube-Shorts-Generator
- AutoShorts: https://github.com/alamshafil/auto-shorts
- auto-yt-shorts: https://github.com/marvinvr/auto-yt-shorts
- ShortGPT: https://github.com/RayVentura/ShortGPT

### Herramientas de edicion
- FFmpeg drawtext: https://www.braydenblackwell.com/blog/ffmpeg-text-rendering
- Editly: https://github.com/mifi/editly
- Remotion: https://github.com/remotion-dev/remotion
- MoviePy: https://github.com/Zulko/moviepy
- pysubs2: https://github.com/tkarabela/pysubs2

### Stock footage sin API (descarga manual)
- Mixkit: https://mixkit.co/free-stock-video/
- Videvo: https://www.videvo.net/
- Coverr: https://coverr.co/
- Life of Vids: https://lifeofvids.com/
- Dareful: https://dareful.com/

### Musica
- Pixabay Music: https://pixabay.com/music/
- YouTube Audio Library: https://studio.youtube.com/channel/UC/music
- Freesound: https://freesound.org/
- Incompetech: https://incompetech.com/music/

### Legal/YouTube
- YouTube Copyright Rules 2026: https://hellothematic.com/how-copyright-works-on-youtube/
- YouTube Shorts Copyright Guide: https://subscribr.ai/p/youtube-shorts-copyright-guide
- YouTube AI Monetization Policy: https://www.knolli.ai/post/youtube-ai-monetization-policy-2025
- YouTube Demonetization 2026: https://mediacube.io/en-US/blog/youtube-demonetization

### TTS local
- Piper TTS: https://github.com/rhasspy/piper (movido a https://github.com/OHF-Voice/piper1-gpl)
- Chatterbox: https://github.com/resemble-ai/chatterbox (23,800 stars, MIT)
- Kokoro: https://github.com/hexgrad/kokoro (6,000 stars, Apache)
- Edge-TTS: https://github.com/rany2/edge-tts (10,300 stars) — usa cloud de Microsoft Edge, sin API key, gratis. NO es local pero es la mas usada en los pipelines open source
- Bark (Suno): https://github.com/suno-ai/bark (39,000 stars, MIT) — genera voz, musica y efectos, muy expresivo, necesita GPU
