# 05 — Publisher: YouTube Shorts

## publishers/youtube.py

Módulo de publicación en YouTube usando OAuth2 y la YouTube Data API v3.

- Autenticación OAuth2 con token persistente
- Upload resumible con chunks de 5MB
- Metadata: título, descripción, tags, categoría, idioma
- Resultado con video_id y URL del Short

## Primera autenticación OAuth (manual, una sola vez)

Ejecutar `auth_youtube.py` en el GMKtec con pantalla/VNC:
```bash
source venv/bin/activate
python auth_youtube.py
# Abrirá navegador → login con finanzasjpg@gmail.com → Permitir
# Guarda el token en credentials/yt_token.json automáticamente
```

Ver código completo en los ficheros fuente.
