from dataclasses import dataclass
from agents.llm_client import generate_json

@dataclass
class VideoMetadata:
    title: str           # Máx 60 chars (se trunca en móvil)
    description: str     # Con keywords SEO + hashtags
    tags: list           # Tags YouTube (máx 500 chars total)

META_PROMPT = """
Eres experto en SEO y viralidad para YouTube Shorts en español.
Canal: "Finanzas Claras" — finanzas personales para españoles.

REGLAS TÍTULO:
- Máximo 60 caracteres
- Empieza con emoji financiero (💰💸📈🏦💡)
- Pregunta O dato impactante O promesa concreta
- Sin clickbait falso

REGLAS DESCRIPCIÓN:
- Primera línea: repite el gancho del vídeo
- Segunda línea en blanco
- 2-3 líneas con keywords naturales
- Línea en blanco
- Hashtags: #shorts + 8-10 del nicho
- Al final: "📲 Suscríbete para más consejos de finanzas"

REGLAS TAGS:
- 10-15 tags en español
- Mix: generales (finanzas, inversión, dinero) + específicos del tema

Responde ÚNICAMENTE en JSON válido. Sin backticks, sin texto adicional.
"""

def generate(topic: str, hook: str, narration: str) -> VideoMetadata:
    user_msg = f"""
Tema: {topic}
Hook: {hook}
Guión (resumen): {narration[:300]}...

Genera metadata viral para YouTube Shorts.

JSON exacto:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}
"""
    data = generate_json(META_PROMPT, user_msg)
    return VideoMetadata(**data)


META_PROMPT_EN = """
You are an expert in SEO and virality for YouTube Shorts in English.
Channel: "Finanzas Claras" — personal finance tips.

TITLE RULES:
- Max 60 characters
- Start with financial emoji (💰💸📈🏦💡)
- Question OR shocking fact OR concrete promise
- No false clickbait

DESCRIPTION RULES:
- First line: repeat the video hook
- Blank line
- 2-3 lines with natural keywords
- Blank line
- Hashtags: #shorts + 8-10 niche tags
- End with: "📲 Subscribe for more finance tips"

TAG RULES:
- 10-15 tags in English
- Mix: general (finance, investing, money) + topic-specific

Respond ONLY in valid JSON. No backticks, no extra text.
"""


def generate_en(topic: str, hook: str, narration_en: str) -> VideoMetadata:
    """Generate English metadata for YouTube Shorts."""
    user_msg = f"""
Topic: {topic}
Hook: {hook}
Script (summary): {narration_en[:300]}...

Generate viral metadata for YouTube Shorts in English.

Exact JSON:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}
"""
    data = generate_json(META_PROMPT_EN, user_msg)
    return VideoMetadata(**data)
