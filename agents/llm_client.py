"""
Cliente LLM unificado: Claude CLI (claude -p) con fallback a Ollama local.
Usa claude -p para aprovechar la suscripción de Claude Code sin pagar API aparte.
"""
import json
import os
import re
import logging
import subprocess
import urllib.request
import urllib.error

logger = logging.getLogger("videobot")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/gmktec/.local/bin/claude")


def _clean_json(raw: str) -> str:
    """Limpia markdown backticks y extrae JSON puro."""
    raw = raw.strip()
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    if not raw.startswith('{'):
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            raw = m.group(0)
    return raw


def generate(system: str, user: str, max_tokens: int = 1500) -> str:
    """
    Genera texto con Claude CLI (claude -p) sin coste API.
    Fallback a Ollama local si Claude CLI no está disponible.
    """
    # Claude CLI primero (mejor calidad, usa suscripción Claude Code)
    try:
        return _claude_cli_generate(system, user)
    except Exception as e:
        logger.warning(f"Claude CLI falló: {e}, intentando Ollama...")

    # Fallback a Ollama local
    try:
        return _ollama_generate(system, user)
    except Exception as e:
        raise RuntimeError(f"Claude CLI y Ollama no disponibles: {e}")


def generate_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Genera y parsea JSON. Robusto ante respuestas con texto extra."""
    raw = generate(system, user, max_tokens)
    cleaned = _clean_json(raw)
    return json.loads(cleaned)


def _claude_cli_generate(system: str, user: str) -> str:
    """Llama a Claude via CLI (claude -p). Usa la suscripción de Claude Code."""
    prompt = f"{system}\n\n{user}"
    result = subprocess.run(
        [CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p falló (code {result.returncode}): {result.stderr[:300]}")
    output = result.stdout.strip()
    if not output:
        raise RuntimeError("claude -p devolvió respuesta vacía")
    logger.info(f"Claude CLI generó {len(output)} chars")
    return output


def _ollama_generate(system: str, user: str) -> str:
    """Llama a Ollama vía HTTP (sin dependencias externas)."""
    url = f"{OLLAMA_HOST}/api/chat"
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 2000,
        },
        "format": "json",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["message"]["content"]
    except urllib.error.URLError as e:
        raise ConnectionError(f"No se puede conectar a Ollama ({OLLAMA_HOST}): {e}")
