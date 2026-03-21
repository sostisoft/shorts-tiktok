"""
pipeline/stock_video.py
Busca y descarga clips de video stock de Pexels y Pixabay.
Reemplaza FLUX.1 + Wan2.1/Ken Burns como fuente de video.

Uso:
    provider = StockVideoProvider()
    clips = provider.get_clips_for_scenes(scenes, work_dir / "clips")

Requiere en .env:
    PEXELS_API_KEY=...
    PIXABAY_API_KEY=...  (opcional, fallback)
"""
import hashlib
import json
import logging
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlencode
import subprocess

import requests

logger = logging.getLogger("videobot.stock_video")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Cache local de clips descargados
CACHE_DIR = Path(os.getenv("STOCK_CACHE_DIR", "assets/stock-videos"))
CACHE_INDEX = CACHE_DIR / "index.json"

# Duracion objetivo de cada clip
CLIP_DURATION = 5  # segundos

# Pexels rate limit: 200 req/hora -> ~3.3 req/seg maximo, usamos 1/seg para seguridad
PEXELS_DELAY = 1.0
PIXABAY_DELAY = 0.7


class StockVideoProvider:
    """Busca y descarga videos stock de Pexels y Pixabay."""

    def __init__(self):
        self._cache = self._load_cache()
        if not PEXELS_API_KEY and not PIXABAY_API_KEY:
            raise RuntimeError(
                "Se necesita al menos PEXELS_API_KEY o PIXABAY_API_KEY en .env"
            )

    # == API publica ============================================================

    def get_clips_for_scenes(
        self,
        scenes: list[dict],
        output_dir: Path,
        clip_duration: int = CLIP_DURATION,
    ) -> list[Path]:
        """
        Para cada escena, busca y descarga un clip de video vertical.
        Devuelve lista de paths a clips MP4 listos para compositing.

        Args:
            scenes: lista de dicts con 'image_prompt' y/o 'text'
            output_dir: directorio donde guardar los clips
            clip_duration: duracion objetivo de cada clip en segundos
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        clip_paths = []

        for i, scene in enumerate(scenes):
            clip_path = output_dir / f"clip_{i:02d}.mp4"
            if clip_path.exists() and clip_path.stat().st_size > 1000:
                logger.info(f"  Clip {i+1}/{len(scenes)} ya existe, saltando")
                clip_paths.append(clip_path)
                continue

            # Extraer keywords de busqueda del prompt de imagen
            keywords = self._extract_keywords(scene)
            logger.info(f"  Clip {i+1}/{len(scenes)}: buscando '{keywords}'...")

            # Buscar en cache primero
            cached = self._find_in_cache(keywords)
            if cached and cached.exists():
                logger.info(f"    Cache hit: {cached.name}")
                self._prepare_clip(cached, clip_path, clip_duration)
                clip_paths.append(clip_path)
                continue

            # Descargar de APIs
            raw_path = output_dir / f"raw_{i:02d}.mp4"
            downloaded = self._download_clip(keywords, raw_path)

            if downloaded:
                self._prepare_clip(raw_path, clip_path, clip_duration)
                self._save_to_cache(raw_path, keywords)
                raw_path.unlink(missing_ok=True)
            else:
                # Fallback: clip negro con texto (nunca deberia pasar)
                logger.warning(f"    No se encontro video para '{keywords}', generando placeholder")
                self._generate_placeholder(clip_path, scene.get("text", ""), clip_duration)

            clip_paths.append(clip_path)

        return clip_paths

    def unload(self):
        """No-op — no hay modelo que descargar."""
        pass

    # == Busqueda en APIs ======================================================

    def _download_clip(self, keywords: str, output_path: Path) -> bool:
        """Intenta descargar un clip de Pexels, luego Pixabay."""
        # Pexels primero (mejor calidad y filtro portrait)
        if PEXELS_API_KEY:
            url = self._search_pexels(keywords)
            if url:
                return self._download_file(url, output_path)

        # Pixabay como fallback
        if PIXABAY_API_KEY:
            url = self._search_pixabay(keywords)
            if url:
                return self._download_file(url, output_path)

        # Intentar con keywords mas genericos
        generic = self._simplify_keywords(keywords)
        if generic != keywords:
            logger.info(f"    Reintentando con keywords genericos: '{generic}'")
            if PEXELS_API_KEY:
                url = self._search_pexels(generic)
                if url:
                    return self._download_file(url, output_path)
            if PIXABAY_API_KEY:
                url = self._search_pixabay(generic)
                if url:
                    return self._download_file(url, output_path)

        return False

    def _search_pexels(self, query: str) -> str | None:
        """Busca en Pexels y devuelve URL de descarga del mejor video vertical."""
        try:
            headers = {"Authorization": PEXELS_API_KEY}
            params = {
                "query": query,
                "orientation": "portrait",
                "size": "medium",
                "per_page": 15,
            }
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
                timeout=15,
            )
            time.sleep(PEXELS_DELAY)

            if r.status_code == 429:
                logger.warning("    Pexels rate limit alcanzado, esperando 60s...")
                time.sleep(60)
                return None

            r.raise_for_status()
            data = r.json()
            videos = data.get("videos", [])

            if not videos:
                logger.info(f"    Pexels: 0 resultados para '{query}'")
                return None

            # Seleccionar un video aleatorio de los resultados (variedad)
            video = random.choice(videos[:min(5, len(videos))])

            # Buscar el mejor archivo: preferir HD vertical
            best_file = self._pick_best_file(video.get("video_files", []))
            if best_file:
                logger.info(f"    Pexels: encontrado ({best_file['width']}x{best_file['height']})")
                return best_file["link"]

            return None
        except Exception as e:
            logger.warning(f"    Pexels error: {e}")
            return None

    def _search_pixabay(self, query: str) -> str | None:
        """Busca en Pixabay y devuelve URL de descarga."""
        try:
            params = {
                "key": PIXABAY_API_KEY,
                "q": query.replace(" ", "+"),
                "video_type": "film",
                "per_page": 10,
                "min_height": 720,
            }
            r = requests.get(
                "https://pixabay.com/api/videos/",
                params=params,
                timeout=15,
            )
            time.sleep(PIXABAY_DELAY)
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", [])

            if not hits:
                logger.info(f"    Pixabay: 0 resultados para '{query}'")
                return None

            # Preferir videos verticales (height > width)
            vertical = [h for h in hits if self._is_vertical_pixabay(h)]
            pool = vertical if vertical else hits

            hit = random.choice(pool[:min(5, len(pool))])

            # Preferir 'large' (1920p), luego 'medium' (1080p)
            videos = hit.get("videos", {})
            for quality in ("large", "medium", "small"):
                if quality in videos and videos[quality].get("url"):
                    w = videos[quality].get("width", 0)
                    h = videos[quality].get("height", 0)
                    logger.info(f"    Pixabay: encontrado {quality} ({w}x{h})")
                    return videos[quality]["url"]

            return None
        except Exception as e:
            logger.warning(f"    Pixabay error: {e}")
            return None

    # == Descarga y preparacion ================================================

    @staticmethod
    def _download_file(url: str, output_path: Path) -> bool:
        """Descarga un archivo por URL."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            size_mb = output_path.stat().st_size / 1e6
            logger.info(f"    Descargado: {output_path.name} ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            logger.warning(f"    Error descargando: {e}")
            output_path.unlink(missing_ok=True)
            return False

    @staticmethod
    def _prepare_clip(
        input_path: Path, output_path: Path, duration: int = 5
    ):
        """
        Prepara un clip stock para compositing:
        - Escalar/crop a 1080x1920 (vertical 9:16)
        - Cortar a duracion objetivo
        - Re-encode H.264
        """
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-t", str(duration),
            "-vf", (
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                "fps=24"
            ),
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-an",  # sin audio (se anade despues)
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg prepare_clip error: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg fallo preparando clip: {result.stderr[-200:]}")

    @staticmethod
    def _generate_placeholder(output_path: Path, text: str, duration: int = 5):
        """Genera un clip negro con texto como ultimo recurso."""
        safe_text = text.replace("'", "").replace(":", "")[:40]
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1080x1920:d={duration}:r=24",
            "-vf", (
                f"drawtext=text='{safe_text}':"
                "fontsize=48:fontcolor=white:"
                "x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    # == Keywords ==============================================================

    @staticmethod
    def _extract_keywords(scene: dict) -> str:
        """Extrae keywords de busqueda de una escena del guion."""
        # Usar stock_keywords si el LLM los genero
        if "stock_keywords" in scene:
            kw = scene["stock_keywords"]
            if isinstance(kw, list):
                return " ".join(kw[:3])
            return str(kw)

        # Extraer de image_prompt (quitar adjetivos cinematograficos)
        prompt = scene.get("image_prompt", "")
        if prompt:
            # Quitar palabras de estilo que no ayudan en busqueda de stock
            noise = {
                "cinematic", "dramatic", "professional", "realistic", "hyperrealistic",
                "ultra", "4k", "hdr", "depth", "field", "bokeh", "shallow",
                "documentary", "style", "moody", "atmospheric", "dark", "ambient",
                "close", "shot", "wide", "medium", "angle", "view", "vertical",
                "9:16", "portrait", "detailed", "high", "quality", "photo",
                "smooth", "camera", "movement", "motion", "subtle", "gentle",
                "pan", "zoom", "dolly", "tracking", "slow", "fast",
                "lighting", "light", "warm", "golden", "blue", "tones",
                "scene", "revealing", "background", "foreground", "focus",
                "resolution", "render", "illustration", "concept",
            }
            words = re.sub(r"[,.:;()\[\]]", " ", prompt.lower()).split()
            keywords = [w for w in words if w not in noise and len(w) > 2]
            # Tomar las 3 primeras palabras significativas
            return " ".join(keywords[:3])

        # Fallback al texto de pantalla — traducir conceptos comunes
        text = scene.get("text", "finance money")
        return text.lower()

    @staticmethod
    def _simplify_keywords(keywords: str) -> str:
        """Simplifica keywords para busqueda mas amplia."""
        # Mapeo de temas financieros a keywords genericos que existen en stock
        mappings = {
            "hipoteca": "mortgage house",
            "ahorro": "saving money piggy bank",
            "inversion": "stock market trading",
            "impuesto": "tax calculator",
            "autonomo": "freelancer laptop",
            "jubilacion": "retirement elderly",
            "pension": "retirement planning",
            "inflacion": "price shopping",
            "cripto": "cryptocurrency bitcoin",
            "presupuesto": "budget planning",
            "deuda": "credit card debt",
            "nomina": "salary paycheck",
            "banco": "bank office",
            "seguro": "insurance document",
            "hacienda": "tax office government",
        }
        kw_lower = keywords.lower()
        for es_word, en_keywords in mappings.items():
            if es_word in kw_lower:
                return en_keywords

        # Si no hay mapeo, traducir las primeras 2 palabras
        words = keywords.split()[:2]
        return " ".join(words) if words else "finance business"

    # == Seleccion de archivos =================================================

    @staticmethod
    def _pick_best_file(video_files: list[dict]) -> dict | None:
        """Elige el mejor archivo de video de Pexels: HD vertical preferido."""
        if not video_files:
            return None

        # Preferir: vertical, HD/Full HD, formato mp4
        scored = []
        for f in video_files:
            w = f.get("width", 0)
            h = f.get("height", 0)
            quality = f.get("quality", "")
            score = 0
            # Vertical (h > w) es muy preferido
            if h > w:
                score += 100
            # HD es buen equilibrio calidad/tamaño
            if quality == "hd":
                score += 50
            elif quality == "sd":
                score += 20
            # Evitar archivos muy grandes (>100MB)
            size = f.get("size", 0)
            if size and size > 100_000_000:
                score -= 30
            scored.append((score, f))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    @staticmethod
    def _is_vertical_pixabay(hit: dict) -> bool:
        """Comprueba si un video de Pixabay es vertical."""
        videos = hit.get("videos", {})
        for quality in ("large", "medium", "small"):
            if quality in videos:
                w = videos[quality].get("width", 0)
                h = videos[quality].get("height", 0)
                if h > w:
                    return True
        return False

    # == Cache local ===========================================================

    def _load_cache(self) -> list[dict]:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if CACHE_INDEX.exists():
            try:
                return json.loads(CACHE_INDEX.read_text())
            except Exception:
                return []
        return []

    def _save_cache(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_INDEX.write_text(json.dumps(self._cache, indent=2, ensure_ascii=False))

    def _find_in_cache(self, keywords: str) -> Path | None:
        """Busca en cache local un clip que matchee los keywords."""
        kw_set = set(keywords.lower().split())
        best_match = None
        best_score = 0

        for entry in self._cache:
            entry_kw = set(entry.get("keywords", "").lower().split())
            if not entry_kw:
                continue
            intersection = kw_set & entry_kw
            if not intersection:
                continue
            score = len(intersection) / len(kw_set | entry_kw)
            # Solo reutilizar si score > 40% y no se ha usado mucho
            if score > 0.4 and score > best_score and entry.get("times_used", 0) < 5:
                best_score = score
                best_match = entry

        if best_match:
            path = CACHE_DIR / best_match["filename"]
            if path.exists():
                best_match["times_used"] = best_match.get("times_used", 0) + 1
                self._save_cache()
                return path

        return None

    def _save_to_cache(self, video_path: Path, keywords: str):
        """Guarda un video descargado en la cache local."""
        # Nombre basado en hash de keywords + timestamp
        kw_hash = hashlib.md5(keywords.encode()).hexdigest()[:8]
        filename = f"stock_{kw_hash}_{os.urandom(2).hex()}.mp4"
        dest = CACHE_DIR / filename

        import shutil
        shutil.copy2(video_path, dest)

        self._cache.append({
            "filename": filename,
            "keywords": keywords,
            "times_used": 0,
            "source": "pexels/pixabay",
            "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        self._save_cache()
        logger.info(f"    Guardado en cache: {filename}")
