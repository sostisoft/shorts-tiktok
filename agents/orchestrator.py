import json
from dataclasses import dataclass
from datetime import date
from agents.llm_client import generate_json


@dataclass
class VideoDecision:
    topic: str              # Tema concreto del vídeo (único, nunca repetido)
    hook: str               # Primera frase — gancho 2 segundos (castellano)
    narration: str          # Guión castellano para TTS (~40 palabras, 15s)
    narration_en: str       # Guión inglés para TTS (~40 palabras, 15s)
    image_prompts: list     # 3 prompts en inglés para FLUX
    style: str              # Estilo visual ("cinematic office", "modern city", etc)
    duration_target: int    # Segundos objetivo (15)

SYSTEM_PROMPT = """
Eres el director de contenido de "Finanzas Claras", un canal de YouTube Shorts
sobre finanzas personales para españoles de 25-45 años.

El canal publica vídeos 100% generados con IA: imágenes sintéticas + narración en off.
Sin cara, sin cámara. Estilo documental moderno.

TONO: Directo, cercano, sin tecnicismos. Como un amigo que sabe de finanzas.
IDIOMA: Castellano neutro (sin modismos regionales)
DURACIÓN: EXACTAMENTE 15 segundos. Ni más ni menos.

REGLA CRÍTICA — NO REPETIR:
Se te dará una lista de TODOS los temas ya publicados.
NUNCA repitas un tema, ni un ángulo similar, ni una reformulación del mismo concepto.

FORMATO DE GANCHO (primeros 2 segundos):
- Pregunta corta que genera curiosidad
- Dato impactante con número concreto
- Afirmación provocadora

GUIÓN: Máximo 40 palabras. Debe leerse en exactamente 12-13 segundos a ritmo natural.
Estructura: gancho (2s) → dato clave (8s) → cierre con CTA implícito (3s).

IMAGEN PROMPTS: 3 escenas realistas, estilo cinematográfico.
SIEMPRE en inglés, muy descriptivos (50-80 palabras cada uno).
Deben ser visualmente distintas entre sí para dar dinamismo al vídeo.

Responde ÚNICAMENTE en JSON válido. Sin backticks, sin texto adicional, sin explicaciones.
"""

TOPIC_PROMPT = """
Se te da un TEMA CONCRETO elegido por el creador del canal.
Tu trabajo es SOLO generar el guión, gancho e image prompts para ese tema.
NO elijas otro tema. Trabaja exclusivamente con el que se te da.

Responde ÚNICAMENTE en JSON válido. Sin backticks, sin texto adicional.
"""


def decide(recent_topics: list[str]) -> VideoDecision:
    """LLM elige tema libremente (modo automático)."""
    user_msg = f"""
Hoy es {date.today().strftime('%A %d de %B de %Y')}.

TEMAS YA PUBLICADOS — PROHIBIDO repetir:
{json.dumps(recent_topics, ensure_ascii=False) if recent_topics else '["(ninguno todavía)"]'}

Decide el siguiente vídeo. EXACTAMENTE 15 segundos, ~40 palabras, 3 image prompts.
Genera DOBLE guión: castellano (acento España) + inglés (acento americano).
Ambos guiones deben transmitir el mismo mensaje pero adaptados culturalmente.

JSON exacto:
{{
  "topic": "título descriptivo ÚNICO",
  "hook": "frase gancho (máx 8 palabras)",
  "narration": "guión de 15s (~40 palabras) en CASTELLANO de España",
  "narration_en": "script 15s (~40 words) in American English",
  "image_prompts": ["prompt 1 inglés", "prompt 2 inglés", "prompt 3 inglés"],
  "style": "estilo visual",
  "duration_target": 15
}}
"""
    data = generate_json(SYSTEM_PROMPT, user_msg)
    return VideoDecision(**data)


def decide_from_topic(topic: str, enfoque: str = None, recent_topics: list[str] = None) -> VideoDecision:
    """LLM genera guión + metadata a partir de un tema dado por el usuario."""
    tema_desc = topic
    if enfoque:
        tema_desc += f" (enfoque: {enfoque})"

    recent = recent_topics or []

    user_msg = f"""
Hoy es {date.today().strftime('%A %d de %B de %Y')}.

TEMA ASIGNADO (NO cambiar): {tema_desc}

Temas anteriores (para no repetir ángulo):
{json.dumps(recent, ensure_ascii=False) if recent else '[]'}

Genera guión + prompts para EXACTAMENTE este tema.
15 segundos, ~40 palabras de narración, 3 image prompts.
Genera DOBLE guión: castellano (acento España) + inglés (acento americano).

JSON exacto:
{{
  "topic": "{topic}",
  "hook": "frase gancho (máx 8 palabras)",
  "narration": "guión de 15s (~40 palabras) en CASTELLANO de España",
  "narration_en": "script 15s (~40 words) in American English",
  "image_prompts": ["prompt 1 inglés", "prompt 2 inglés", "prompt 3 inglés"],
  "style": "estilo visual",
  "duration_target": 15
}}
"""
    data = generate_json(SYSTEM_PROMPT + "\n" + TOPIC_PROMPT, user_msg)
    return VideoDecision(**data)
