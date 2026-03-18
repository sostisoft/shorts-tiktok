"""
Banco de imágenes con cache semi-inteligente.

Guarda cada imagen generada con su prompt en un índice JSON.
Antes de generar una nueva, busca si hay alguna similar en el banco.
Reutiliza con moderación: máximo 1 imagen cacheada por vídeo.
"""
import json
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("videobot")

BANK_DIR = Path("assets/image-bank")
INDEX_FILE = BANK_DIR / "index.json"

# Palabras clave financieras para matching
FINANCE_KEYWORDS = {
    "office", "desk", "computer", "laptop", "phone", "screen",
    "chart", "graph", "stock", "trading", "money", "cash", "coins",
    "bank", "credit", "card", "wallet", "savings", "piggy",
    "house", "apartment", "building", "city", "street", "spain",
    "couple", "family", "person", "man", "woman", "young",
    "document", "contract", "signing", "paperwork", "tax",
    "investment", "portfolio", "finance", "financial", "market",
    "retirement", "pension", "mortgage", "debt", "loan",
}


def _load_index() -> list[dict]:
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return []


def _save_index(index: list[dict]):
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))


def _extract_keywords(prompt: str) -> set[str]:
    words = set(prompt.lower().split())
    return words & FINANCE_KEYWORDS


def _similarity(keywords_a: set[str], keywords_b: set[str]) -> float:
    if not keywords_a or not keywords_b:
        return 0.0
    intersection = keywords_a & keywords_b
    union = keywords_a | keywords_b
    return len(intersection) / len(union)


def save_to_bank(image_path: Path, prompt: str, topic: str):
    """Guarda una imagen generada en el banco con su metadata."""
    index = _load_index()
    BANK_DIR.mkdir(parents=True, exist_ok=True)

    # Nombre basado en hash del prompt
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{timestamp}_{prompt_hash}.png"
    dest = BANK_DIR / filename

    shutil.copy2(image_path, dest)

    index.append({
        "filename": filename,
        "prompt": prompt,
        "topic": topic,
        "keywords": list(_extract_keywords(prompt)),
        "times_used": 0,
        "created_at": datetime.now().isoformat(),
    })
    _save_index(index)
    logger.info(f"  Imagen guardada en banco: {filename}")


def find_cached(prompt: str, max_uses: int = 2) -> Path | None:
    """
    Busca una imagen similar en el banco.
    Devuelve Path si encuentra match con >50% similitud y <max_uses usos.
    Devuelve None si no hay match bueno (se generará nueva).
    """
    index = _load_index()
    if not index:
        return None

    query_keywords = _extract_keywords(prompt)
    if not query_keywords:
        return None

    best_match = None
    best_score = 0.0

    for entry in index:
        if entry.get("times_used", 0) >= max_uses:
            continue

        entry_keywords = set(entry.get("keywords", []))
        score = _similarity(query_keywords, entry_keywords)

        if score > best_score:
            best_score = score
            best_match = entry

    # Solo reutilizar si similitud > 50%
    if best_match and best_score > 0.5:
        path = BANK_DIR / best_match["filename"]
        if path.exists():
            # Marcar como usada
            best_match["times_used"] = best_match.get("times_used", 0) + 1
            _save_index(index)
            logger.info(f"  Cache hit ({best_score:.0%}): {best_match['filename']}")
            return path

    return None


def generate_with_cache(
    image_gen,
    prompts: list[str],
    job_id: str,
    output_dir: Path,
    topic: str,
    max_cached_per_video: int = 1,
) -> list[Path]:
    """
    Genera imágenes usando el banco como cache.
    Máximo max_cached_per_video imágenes del banco por vídeo.
    El resto se generan frescas y se guardan en el banco.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    cached_count = 0

    for i, prompt in enumerate(prompts):
        dest = output_dir / f"img_{i:02d}.png"

        # Intentar cache (máximo 1 por vídeo)
        if cached_count < max_cached_per_video:
            cached = find_cached(prompt)
            if cached:
                shutil.copy2(cached, dest)
                paths.append(dest)
                cached_count += 1
                logger.info(f"  Imagen {i+1}/{len(prompts)}: reutilizada del banco")
                continue

        # Generar nueva — delega a ImageGenerator.generate() para un solo prompt
        logger.info(f"  Imagen {i+1}/{len(prompts)}: generando nueva...")
        generated = image_gen.generate([prompt], job_id, output_dir)
        if generated:
            # generate() guarda como img_00.png, renombrar al índice correcto
            generated[0].rename(dest)

        paths.append(dest)

        # Guardar en banco para futuro
        save_to_bank(dest, prompt, topic)

    return paths
