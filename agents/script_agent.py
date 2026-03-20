"""
agents/script_agent.py
Genera guiones para Shorts de finanzas personales.
- Primario: Ollama local (Qwen 2.5 14B)
- Fallback: Claude API (anthropic SDK)
Output: JSON con título, descripción, escenas e imagen-prompts
"""
import json
import logging
import os
import re

import requests

logger = logging.getLogger("videobot.script_agent")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """Eres el guionista de "Finanzas Claras", un canal de YouTube Shorts en castellano de España.
Creas contenido de finanzas personales breve, directo y accionable.
Cada consejo sigue el formato: "Haz X, porque Y, y conseguirás Z."
Siempre respondes SOLO con JSON válido, sin texto adicional ni bloques de código markdown."""

SCRIPT_PROMPT_TEMPLATE = """Crea un guión para un YouTube Short de finanzas personales.

Tema sugerido: {topic}

El vídeo dura EXACTAMENTE 20 segundos. Genera un JSON con esta estructura EXACTA:
{{
  "title": "Título gancho para YouTube (max 60 chars)",
  "description": "Descripción SEO para YouTube (max 200 chars, incluye hashtags)",
  "narration": "Narración completa en castellano de España. 45-55 palabras. Tono con autoridad pero cercano. Formato: gancho con dato → consejo accionable con números → SIEMPRE terminar con 'Te lo dice, arroba finanzas jpg.'",
  "scenes": [
    {{
      "text": "Frase corta que aparece en pantalla (max 6 palabras)",
      "image_prompt": "Prompt en inglés para generar imagen con Flux. Cinematográfico, sin texto. Vertical 9:16."
    }}
  ],
  "tags": ["#FinanzasPersonales", "#DineroInteligente", "#Shorts"]
}}

IMPORTANTE: Genera exactamente 4 escenas. Cada escena dura 5 segundos.
La narración SIEMPRE termina con "Te lo dice, arroba finanzas jpg." """


class ScriptAgent:
    def generate(self, topic: str | None = None) -> dict:
        """
        Genera un guión completo para un Short.

        Args:
            topic: Tema sugerido. None = el agente elige uno de su banco de temas.

        Returns:
            dict con title, description, narration, scenes[], tags[]
        """
        if topic is None:
            topic = self._pick_topic()

        prompt = SCRIPT_PROMPT_TEMPLATE.format(topic=topic)
        logger.info(f"Generando guión sobre: {topic}")

        # Intentar Ollama primero
        script = self._try_ollama(prompt)
        if script is None:
            logger.warning("Ollama falló o no disponible, usando Claude API como fallback")
            script = self._try_claude(prompt)

        if script is None:
            raise RuntimeError("No se pudo generar el guión (Ollama y Claude API fallaron)")

        logger.info(f"Guión generado: '{script.get('title', 'sin título')}'")
        return script

    # ── Ollama ────────────────────────────────────────────────────────────────

    def _try_ollama(self, prompt: str) -> dict | None:
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1024,
                    },
                },
                timeout=120,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            return self._parse_json(raw)
        except Exception as e:
            logger.warning(f"Ollama error: {e}")
            return None

    # ── Claude API ────────────────────────────────────────────────────────────

    def _try_claude(self, prompt: str) -> dict | None:
        try:
            import anthropic
            client = anthropic.Anthropic()
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
            return self._parse_json(raw)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    # ── Utilidades ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        """Extrae y parsea JSON de la respuesta del LLM."""
        # Eliminar bloques markdown si los hay
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        raw = re.sub(r"```\s*$", "", raw).strip()

        # Buscar el primer { y el último }
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error(f"No se encontró JSON en la respuesta: {raw[:200]}")
            return None

        try:
            data = json.loads(raw[start:end])
            # Validar campos mínimos
            required = {"title", "narration", "scenes"}
            if not required.issubset(data.keys()):
                missing = required - data.keys()
                logger.error(f"JSON incompleto, faltan: {missing}")
                return None
            if not isinstance(data["scenes"], list) or len(data["scenes"]) == 0:
                logger.error("scenes debe ser una lista no vacía")
                return None
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON inválido: {e}\nRaw: {raw[:500]}")
            return None

    @staticmethod
    def _pick_topic() -> str:
        """Selecciona un tema de finanzas del banco de temas."""
        import random
        topics = [
            "Cómo ahorrar el 20% de tu sueldo automáticamente",
            "El error que cometen el 90% de los que invierten por primera vez",
            "Regla del 50-30-20 para gestionar tu dinero",
            "Por qué el interés compuesto te hace rico (o pobre)",
            "3 gastos que debes eliminar para mejorar tus finanzas",
            "La diferencia entre activos y pasivos que nadie te enseña",
            "Cómo crear un fondo de emergencia en 3 meses",
            "Inversión en fondos indexados para principiantes",
            "Cómo negociar un aumento de sueldo con éxito",
            "El secreto de las personas que alcanzan la libertad financiera",
            "Por qué deberías tener múltiples fuentes de ingreso",
            "Cómo eliminar deudas con el método bola de nieve",
            "ETF vs acciones individuales: qué te conviene más",
            "El coste oculto de no invertir tus ahorros",
            "Automatiza tus finanzas y deja de preocuparte por el dinero",
        ]
        return random.choice(topics)
