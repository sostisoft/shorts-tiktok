"""
saas/providers/script/claude_api.py
Script generation via Anthropic Claude API with template support.
"""
import json
import logging
import re

import anthropic

from saas.config import get_settings
from saas.providers.script.templates import get_template

logger = logging.getLogger("saas.providers.script")

BASE_SYSTEM_PROMPT = """Eres un guionista viral de contenido corto (TikTok, Reels, YouTube Shorts).
Tu único objetivo: que el espectador NO deslice. Cada segundo cuenta.

Respondes SOLO con JSON válido. Sin texto extra, sin bloques markdown."""

SCRIPT_TEMPLATE = """Crea un guión VIRAL para un Short/Reel/TikTok.

TEMA: {topic}
IDIOMA: {language}

INSTRUCCIONES DE ESTILO:
{style_instructions}

FORMATO: {duration} segundos ({scene_count} escenas), vertical 9:16.

Genera este JSON EXACTO:
{{
  "title": "Título clickbait pero real, max 60 chars.",
  "description": "Descripción SEO, max 200 chars, con hashtags.",
  "narration": "Narración completa para {duration} segundos. TERMINA con cierre del canal.",
  "scenes": [
    {{
      "text": "Frase CORTA pantalla (max 5 palabras)",
      "image_prompt": "Cinematic scene in English for AI image gen. Vertical 9:16, no text. {visual_style}",
      "stock_keywords": "2-3 English keywords for stock video search"
    }}
  ],
  "tags": ["#tag1", "#tag2"]
}}

REGLAS: Exactamente {scene_count} escenas. Cifras REALES y CONCRETAS."""


def _build_prompt(topic: str, style: str, language: str) -> tuple[str, str]:
    """Build system prompt and user prompt from template config."""
    tmpl = get_template(style)

    user_prompt = SCRIPT_TEMPLATE.format(
        topic=topic,
        language=language,
        style_instructions=tmpl["style_instructions"],
        duration=tmpl["duration_seconds"],
        scene_count=tmpl["scene_count"],
        visual_style=tmpl["visual_style"],
    )

    return BASE_SYSTEM_PROMPT, user_prompt


def _parse_json(raw: str) -> dict | None:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    raw = re.sub(r"```\s*$", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        data = json.loads(raw[start:end])
        if not {"title", "narration", "scenes"}.issubset(data.keys()):
            return None
        if not isinstance(data["scenes"], list) or len(data["scenes"]) == 0:
            return None
        return data
    except json.JSONDecodeError:
        return None


def _post_process_script(script: dict, style: str) -> dict:
    """Add visual_style suffix to image prompts based on template."""
    tmpl = get_template(style)
    visual = tmpl.get("visual_style", "")
    if visual:
        for scene in script.get("scenes", []):
            prompt = scene.get("image_prompt", "")
            if visual.lower() not in prompt.lower():
                scene["image_prompt"] = f"{prompt}. {visual}"
    return script


class ClaudeHaikuScriptProvider:
    """Script generation with Claude Haiku (low cost)."""

    async def generate(self, topic: str, style: str, language: str) -> dict:
        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        system_prompt, user_prompt = _build_prompt(topic, style, language)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text
        script = _parse_json(raw)
        if script is None:
            raise RuntimeError("Script generation failed: invalid JSON from Claude Haiku")

        script = _post_process_script(script, style)
        logger.info(f"Script generated (Haiku, {style}): '{script.get('title', 'untitled')}'")
        return script


class ClaudeSonnetScriptProvider:
    """Script generation with Claude Sonnet (higher quality)."""

    async def generate(self, topic: str, style: str, language: str) -> dict:
        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        system_prompt, user_prompt = _build_prompt(topic, style, language)

        message = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text
        script = _parse_json(raw)
        if script is None:
            raise RuntimeError("Script generation failed: invalid JSON from Claude Sonnet")

        script = _post_process_script(script, style)
        logger.info(f"Script generated (Sonnet, {style}): '{script.get('title', 'untitled')}'")
        return script
