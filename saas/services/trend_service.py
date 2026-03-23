"""
saas/services/trend_service.py
Trend intelligence — topic suggestions via Claude + optional Google Trends.
"""
import json
import logging
import re

import anthropic

from saas.config import get_settings

logger = logging.getLogger("saas.services.trends")

TREND_SYSTEM_PROMPT = """Eres un analista de tendencias de contenido digital especializado en YouTube Shorts, TikTok y Reels.
Tu trabajo es sugerir temas VIRALES y RELEVANTES para creadores de contenido.

Respondes SOLO con JSON válido. Sin texto extra."""

TREND_USER_PROMPT = """Sugiere {count} temas VIRALES para YouTube Shorts en el nicho de "{niche}".

Para cada tema:
1. Debe ser específico y accionable (no genérico)
2. Debe tener potencial viral en 2026
3. Incluye cifras o datos reales cuando sea posible
4. Considera tendencias actuales y estacionales

Genera este JSON:
{{
  "suggestions": [
    {{
      "topic": "Tema específico y concreto para un Short",
      "reasoning": "Por qué este tema tiene potencial viral ahora",
      "estimated_interest": "high|medium|low"
    }}
  ]
}}

REGLAS:
- Exactamente {count} sugerencias
- Variedad: mezcla datos impactantes, historias, tips prácticos, mitos vs realidad
- Los topics deben ser en español (España) si el nicho es en español
- Cada topic debe poder ser un Short de 20 segundos"""


class TrendService:

    @staticmethod
    async def suggest_topics(niche: str, count: int = 10) -> list[dict]:
        """Generate topic suggestions using Claude."""
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        prompt = TREND_USER_PROMPT.format(niche=niche, count=count)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=TREND_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        suggestions = TrendService._parse_suggestions(raw)

        logger.info(f"Generated {len(suggestions)} trend suggestions for '{niche}'")
        return suggestions

    @staticmethod
    def _parse_suggestions(raw: str) -> list[dict]:
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        raw = re.sub(r"```\s*$", "", raw).strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return []
        try:
            data = json.loads(raw[start:end])
            suggestions = data.get("suggestions", [])
            return [
                {
                    "topic": s.get("topic", ""),
                    "reasoning": s.get("reasoning", ""),
                    "estimated_interest": s.get("estimated_interest", "medium"),
                }
                for s in suggestions
                if s.get("topic")
            ]
        except json.JSONDecodeError:
            return []
