"""
Cliente LLM unificado: Ollama (local) con fallback opcional a Claude API.
Usa OLLAMA_HOST para conectar al servidor Ollama del host desde Docker.
"""
import json
import os
import re
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("videobot")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")


def _clean_json(raw: str) -> str:
    """Limpia markdown backticks y extrae JSON puro."""
    raw = raw.strip()
    # Quitar ```json ... ``` o ``` ... ```
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    # Intentar encontrar el primer { ... } si hay texto extra
    if not raw.startswith('{'):
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            raw = m.group(0)
    return raw


def generate(system: str, user: str, max_tokens: int = 1500) -> str:
    """
    Genera texto con Ollama (Qwen 2.5 14B local).
    Fallback a Claude API si ANTHROPIC_API_KEY está configurada y Ollama falla.
    """
    # Intentar Ollama primero
    try:
        return _ollama_generate(system, user)
    except Exception as e:
        logger.warning(f"Ollama falló: {e}")

        # Fallback a Claude API si hay key configurada
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            logger.info("Usando Claude API como fallback...")
            return _claude_generate(system, user, max_tokens, api_key)

        raise RuntimeError(f"Ollama no disponible y no hay ANTHROPIC_API_KEY: {e}")


def generate_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Genera y parsea JSON. Robusto ante respuestas con texto extra."""
    raw = generate(system, user, max_tokens)
    cleaned = _clean_json(raw)
    return json.loads(cleaned)


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


def _claude_generate(system: str, user: str, max_tokens: int, api_key: str) -> str:
    """Fallback a Claude API."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()
