# 05 — Publisher: Subida a YouTube Shorts

> Documento 5 de 6 del proyecto VideoBot "Finanzas Claras".
> Cubre la configuración completa de Google Cloud, OAuth2, subida a YouTube
> y preparación multi-plataforma (TikTok, Instagram).

---

## 1. Prerequisitos: Google Cloud Console

### 1.1 Crear el proyecto `finanzas-oc-yt`

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Iniciar sesión con `finanzasjpg@gmail.com`
3. En la barra superior, hacer clic en el selector de proyecto → **Nuevo proyecto**
4. Nombre del proyecto: `finanzas-oc-yt`
5. Organización: dejar por defecto (sin organización)
6. Hacer clic en **Crear**

### 1.2 Habilitar YouTube Data API v3

1. Dentro del proyecto `finanzas-oc-yt`, ir al menú lateral:
   **APIs y servicios → Biblioteca**
2. Buscar `YouTube Data API v3`
3. Seleccionar el resultado y hacer clic en **Habilitar**
4. Esperar a que se active (aparecerá el dashboard de la API)

### 1.3 Configurar pantalla de consentimiento OAuth

Antes de crear credenciales, hay que configurar la pantalla de consentimiento:

1. Ir a **APIs y servicios → Pantalla de consentimiento OAuth**
2. Seleccionar tipo **Externo** (no hace falta Google Workspace)
3. Rellenar:
   - Nombre de la aplicación: `VideoBot Finanzas Claras`
   - Correo de asistencia: `finanzasjpg@gmail.com`
   - Correo del desarrollador: `finanzasjpg@gmail.com`
4. En **Ámbitos (Scopes)**: añadir `https://www.googleapis.com/auth/youtube.upload`
5. En **Usuarios de prueba**: añadir `finanzasjpg@gmail.com`
6. Guardar y continuar

> **Nota**: Mientras la app esté en modo "Testing", solo los usuarios de prueba
> pueden autorizar. Para producción se puede solicitar verificación, pero para
> un solo canal propio no es necesario.

---

## 2. Obtener credenciales OAuth 2.0

1. Ir a **APIs y servicios → Credenciales**
2. Clic en **+ Crear credenciales → ID de cliente de OAuth**
3. Tipo de aplicación: **Aplicación de escritorio** (Desktop app)
4. Nombre: `videobot-desktop`
5. Clic en **Crear**
6. Aparecerá un diálogo con el Client ID y Client Secret
7. Hacer clic en **Descargar JSON**
8. Se descargará un fichero con nombre tipo `client_secret_XXXX.json`

---

## 3. Colocar el fichero de credenciales

Renombrar el JSON descargado y colocarlo en la ruta esperada:

```bash
mkdir -p credentials/
mv ~/Downloads/client_secret_*.json credentials/yt_finanzas.json
```

La ruta final debe ser:

```
shorts/
├── credentials/
│   └── yt_finanzas.json     ← fichero OAuth descargado de Google Cloud
```

La ruta se configura con la variable `CREDENTIALS_DIR` (por defecto `credentials/`):

```python
# publishers/youtube_publisher.py
CREDENTIALS_DIR = Path(os.getenv("CREDENTIALS_DIR", "credentials"))
CLIENT_SECRETS = CREDENTIALS_DIR / "yt_finanzas.json"
TOKEN_PICKLE   = CREDENTIALS_DIR / "yt_token.pkl"
```

> **IMPORTANTE**: Nunca subir `yt_finanzas.json` ni `yt_token.pkl` a Git.
> Ambos están en `.gitignore`.

---

## 4. Primera autorización OAuth (una sola vez)

El flujo OAuth requiere un navegador la primera vez. Ejecutar en el GMKtec
con acceso a pantalla (directamente, VNC, o SSH con X forwarding):

```bash
cd ~/shorts
source venv/bin/activate
python auth_youtube.py
```

### Qué hace `auth_youtube.py`

```python
from publishers.youtube import _get_service

service = _get_service()
channel = service.channels().list(part="snippet", mine=True).execute()
name = channel["items"][0]["snippet"]["title"]
print(f"Autorizado correctamente. Canal: {name}")
```

1. Llama a `_get_service()`, que detecta que no hay token guardado
2. Ejecuta `InstalledAppFlow.from_client_secrets_file()` con el scope
   `youtube.upload`
3. Abre un servidor HTTP local en el puerto 8080 y lanza el navegador
   en la URL de Google:
   ```
   https://accounts.google.com/o/oauth2/auth?...&redirect_uri=http://localhost:8080/...
   ```
4. El usuario inicia sesión con `finanzasjpg@gmail.com`
5. Google muestra la pantalla de consentimiento: "VideoBot Finanzas Claras
   quiere acceder a tu cuenta de YouTube"
6. El usuario hace clic en **Permitir** (puede que aparezca un aviso de
   "app no verificada" — clic en "Avanzado → Ir a VideoBot")
7. Google redirige a `localhost:8080` con el código de autorización
8. El script intercambia el código por tokens (access + refresh)
9. Guarda el token en `credentials/yt_token.json`
10. Imprime el nombre del canal para confirmar que funciona

### Si no hay navegador disponible (servidor headless)

Opción 1: Conectar por VNC al GMKtec y ejecutar allí.

Opción 2: Usar SSH tunnel desde una máquina con navegador:
```bash
# En la máquina local (con navegador)
ssh -L 8080:localhost:8080 user@gmktec

# En el GMKtec (por SSH)
python auth_youtube.py
# Copiar la URL que aparece y abrirla en el navegador local
```

---

## 5. Token: dónde se guarda y cuánto dura

### Ficheros de token

Existen dos implementaciones con formatos distintos:

| Módulo | Fichero de token | Formato |
|--------|-----------------|---------|
| `publishers/youtube.py` | `credentials/yt_token.json` | JSON (Credentials.to_json) |
| `publishers/youtube_publisher.py` | `credentials/yt_token.pkl` | Pickle (pickle.dump) |

El scheduler (`runner.py`) usa `youtube_publisher.py`, por lo que el token
operativo es `credentials/yt_token.pkl`.

### Duración y renovación

- **Access token**: dura **1 hora** (3600 segundos)
- **Refresh token**: **no expira** mientras la app esté activa y el usuario
  no revoque el acceso
- El código renueva automáticamente el access token usando el refresh token:

```python
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
```

- Después de renovar, se sobreescribe el fichero de token
- **No es necesario volver a autorizar manualmente** salvo que:
  - Se revoque el acceso desde [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
  - Se borren las credenciales del disco
  - Google invalide el refresh token (raro, ocurre si la app lleva 6 meses inactiva)

---

## 6. Subida manual de prueba

```bash
cd ~/shorts
source venv/bin/activate

# Publicar el siguiente vídeo pendiente de la cola
python main.py publish
```

### Qué ocurre internamente

1. `main.py publish` llama a `publish_only()` en `scheduler/runner.py`
2. `_publish_next_pending()` busca en SQLite el vídeo más antiguo con
   `status = PENDING`
3. Verifica que el fichero `.mp4` existe en `output/pending/`
4. Instancia `YouTubePublisher` y llama a `upload()` con:
   - `video_path`: ruta al `.mp4`
   - `title`: título del vídeo (truncado a 100 caracteres)
   - `description`: descripción + hashtag `#Shorts`
   - `tags`: etiquetas del guión + `["Shorts", "FinanzasPersonales", "FinanzasClaras"]`
   - `privacy`: `"public"` por defecto
5. La subida es **resumable** en chunks de 5 MB (`MediaFileUpload`)
6. Al completar:
   - Actualiza el registro en SQLite: `status = PUBLISHED`, `youtube_id`, `published_at`
   - Mueve el fichero de `output/pending/` a `output/published/`
   - Loguea la URL: `https://youtube.com/watch?v={video_id}`

### Para generar + publicar en un solo paso

```bash
python main.py run
```

---

## 7. Límites de la YouTube Data API v3

### Cuota diaria

| Concepto | Unidades |
|----------|----------|
| Cuota diaria total | **10,000 unidades** |
| Coste por upload (`videos.insert`) | **~1,600 unidades** |
| Máximo teórico de uploads/día | **6 vídeos** |
| Objetivo del bot | **2-3 vídeos/día** (holgura suficiente) |

### Desglose del coste de un upload

- `videos.insert` (snippet + status): ~1,600 unidades
- `videos.list` (consulta): 1 unidad
- `channels.list` (auth check): 1 unidad

### Configuración de seguridad

```python
# scheduler/runner.py
MAX_VIDEOS_PER_NIGHT = int(os.getenv("MAX_VIDEOS_PER_NIGHT", "6"))
```

El scheduler publica 3 veces al día (09:00, 14:00, 19:00 Madrid), un vídeo
cada vez. Con 3 uploads/día se consumen ~4,800 unidades, dejando margen para
reintentos y consultas.

### Si se agota la cuota

- La API devuelve error `403 quotaExceeded`
- El vídeo queda en `output/pending/` con `status = ERROR` en la DB
- Se reintenta en la siguiente ventana de publicación (la cuota se resetea
  a medianoche hora del Pacífico — PST/PDT)

---

## 8. Gestión de errores y reintentos

### Flujo ante un fallo de publicación

```
upload() lanza excepción
  → except captura el error
  → video.status = ERROR
  → video.error_message = str(e)[:500]
  → session.commit()
  → El fichero .mp4 NO se mueve — permanece en output/pending/
  → Devuelve None
```

### Dónde queda el vídeo

| Situación | Estado en DB | Fichero en disco |
|-----------|-------------|-----------------|
| Generado, pendiente | `PENDING` | `output/pending/{job_id}.mp4` |
| Publicado con éxito | `PUBLISHED` | `output/published/{job_id}.mp4` |
| Error al publicar | `ERROR` | `output/pending/{job_id}.mp4` (no se mueve) |
| Fichero no encontrado | `ERROR` | No existe en disco |

### Cómo reintentar

Actualmente, los vídeos con `status = ERROR` no se reintentan automáticamente
(la query filtra solo por `PENDING`). Para reintentar manualmente:

```bash
# Opción 1: Cambiar el estado en la DB
sqlite3 db/videobot.db "UPDATE videos SET status='pending', error_message=NULL WHERE job_id='XXXXXXXX';"
python main.py publish

# Opción 2: Generar + publicar de nuevo
python main.py run
```

### Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `FileNotFoundError: yt_finanzas.json` | No se descargaron las credenciales OAuth | Ver sección 2 y 3 |
| `403 quotaExceeded` | Se superó la cuota diaria | Esperar al reset (medianoche PST) |
| `403 forbidden` | Token revocado o scope insuficiente | Re-ejecutar `python auth_youtube.py` |
| `400 uploadLimitExceeded` | Demasiados uploads en poco tiempo | Espaciar las subidas |
| `Connection error` | Sin internet o DNS | Verificar conectividad |

---

## 9. El hashtag #Shorts — clasificación de YouTube

### Por qué es crítico

YouTube usa el hashtag `#Shorts` en la descripción como una de las señales
principales para clasificar un vídeo como Short y mostrarlo en el feed de
Shorts. Sin este hashtag, el vídeo puede quedar como vídeo normal y perder
toda la visibilidad del algoritmo de Shorts.

### Cómo lo implementa el código

**En `youtube_publisher.py`** (usado por el scheduler):
```python
if "#Shorts" not in description:
    description = f"{description}\n\n#Shorts #FinanzasPersonales"
```

**En `youtube.py`** (módulo alternativo):
```python
if "#shorts" not in description.lower():
    description += "\n\n#shorts"
```

Ambos módulos garantizan que el hashtag siempre esté presente, incluso si el
agente LLM no lo incluyó en el guión.

### Requisitos adicionales para Shorts

Además del hashtag, YouTube requiere:
- **Formato vertical**: ratio 9:16 (1080x1920 píxeles)
- **Duración**: máximo 60 segundos (idealmente 30-50 segundos)
- El pipeline genera vídeos que cumplen ambos requisitos automáticamente

### Tags adicionales

El publisher añade siempre estas etiquetas al array de tags:
```python
tags = (tags or []) + ["Shorts", "FinanzasPersonales", "FinanzasClaras"]
```

---

## 10. Preparación multi-plataforma

El directorio `publishers/` incluye módulos para tres plataformas:

```
publishers/
├── __init__.py
├── youtube_publisher.py   ← activo (usado por runner.py)
├── youtube.py             ← módulo alternativo con PublishResult
├── tiktok.py              ← implementado, pendiente de auth
└── instagram.py           ← implementado, pendiente de auth
```

### TikTok (`tiktok.py`)

- Usa la **Content Posting API v2** de TikTok
- Upload chunked (10 MB por chunk)
- Requiere access token en `credentials/tiktok_token.json` o variable
  `TIKTOK_ACCESS_TOKEN`
- Interfaz: `publish(video_path, title, description, tags) → TikTokResult`
- Estado: **código completo, pendiente de registrar app en TikTok for Developers**

### Instagram Reels (`instagram.py`)

- Usa la **Graph API v21.0** de Meta (Instagram)
- Upload resumable vía `rupload.facebook.com`
- Flujo en 3 pasos: subir vídeo → crear container → esperar procesamiento → publicar
- Requiere `INSTAGRAM_USER_ID` + `INSTAGRAM_ACCESS_TOKEN` (o fichero
  `credentials/instagram_token.json`)
- Interfaz: `publish(video_path, title, description, tags) → InstagramResult`
- Estado: **código completo, pendiente de crear app en Meta for Developers**

### Interfaz común

Los tres módulos comparten la misma firma de función:

```python
def publish(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
) -> Result  # PublishResult / TikTokResult / InstagramResult
```

Cuando se activen TikTok e Instagram, solo hay que modificar
`_publish_next_pending()` en `runner.py` para llamar a los tres publishers
en secuencia.

---

## Resumen de ficheros relevantes

| Fichero | Propósito |
|---------|-----------|
| `publishers/youtube_publisher.py` | Publisher principal (clase YouTubePublisher) |
| `publishers/youtube.py` | Publisher alternativo (funciones sueltas, PublishResult) |
| `publishers/tiktok.py` | Publisher TikTok (implementado, sin auth) |
| `publishers/instagram.py` | Publisher Instagram Reels (implementado, sin auth) |
| `auth_youtube.py` | Script de autorización OAuth inicial |
| `credentials/yt_finanzas.json` | Credenciales OAuth de Google Cloud |
| `credentials/yt_token.pkl` | Token OAuth guardado (auto-renovable) |
| `credentials/yt_token.json` | Token alternativo (formato JSON) |
| `scheduler/runner.py` | Orquestador que llama a YouTubePublisher |
| `main.py` | Punto de entrada (`python main.py publish`) |
