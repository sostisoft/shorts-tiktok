"""
agents/script_agent.py
Genera guiones para Shorts de finanzas personales.
- Primario: Claude CLI (claude -p) via llm_client
- Fallback: Ollama local (Qwen 2.5 14B)
Output: JSON con título, descripción, escenas e imagen-prompts
"""
import json
import logging
import re

from agents.llm_client import generate

logger = logging.getLogger("videobot.script_agent")

SYSTEM_PROMPT = """Eres un guionista viral de contenido corto (TikTok, Reels, YouTube Shorts) para el canal "Finanzas Claras" (@finanzasjpg).
Tu único objetivo: que el espectador NO deslice. Cada segundo cuenta.

ESTILO:
- Hablas en castellano de España, tono directo y cercano, como un colega que sabe de pasta.
- Abres SIEMPRE con un gancho que duela o sorprenda: una pregunta retórica, un dato impactante, o un "error que cometes".
- NUNCA frases motivacionales vacías. SIEMPRE cifras reales: euros, porcentajes, plazos concretos.
- El consejo debe ser ACCIONABLE HOY: "haz esto con X€ y en Y meses tendrás Z€".
- Cierras SIEMPRE con: "Te lo dice, arroba finanzas jpg."

Respondes SOLO con JSON válido. Sin texto extra, sin bloques markdown, sin explicaciones."""

SCRIPT_PROMPT_TEMPLATE = """Crea un guión VIRAL para un Short/Reel/TikTok de finanzas personales.

TEMA: {topic}

FORMATO DEL VÍDEO:
- Duración: 20 segundos exactos (4 escenas × 5 segundos)
- Vertical 9:16 (móvil a pantalla completa)
- Subtítulos grandes estilo TikTok (las frases de "text" aparecen sobreimpresas)
- Voz en off narrando (campo "narration")
- Clips de vídeo stock o imágenes IA de fondo (campos "image_prompt" y "stock_keywords")

ESTRUCTURA DEL GANCHO (sigue este patrón):
1. ESCENA 1 (0-5s): GANCHO — dato que rompe esquemas o pregunta que duele. El espectador decide si se queda o desliza aquí.
2. ESCENA 2 (5-10s): PROBLEMA — por qué esto importa, qué pierdes si no actúas.
3. ESCENA 3 (10-15s): SOLUCIÓN — el consejo concreto con cifras reales.
4. ESCENA 4 (15-20s): CTA — resultado + cierre "Te lo dice, arroba finanzas jpg."

Genera este JSON EXACTO:
{{
  "title": "Título clickbait pero real, max 60 chars. Usa números y urgencia.",
  "description": "Descripción SEO para YouTube, max 200 chars, con hashtags relevantes.",
  "narration": "Narración completa, 45-55 palabras. Castellano de España. Tono: como si hablaras a un amigo en un bar pero con datos duros. TERMINA con 'Te lo dice, arroba finanzas jpg.'",
  "scenes": [
    {{
      "text": "Frase CORTA pantalla (max 5 palabras, IMPACTANTE)",
      "image_prompt": "Cinematic photo/scene in English for AI image gen. Vertical 9:16, no text, dramatic lighting, relatable situation.",
      "stock_keywords": "2-3 English keywords for Pexels stock video. FILMABLE real scenes, never abstract concepts (good: 'woman checking phone banking app', bad: 'financial freedom')"
    }}
  ],
  "tags": ["#FinanzasPersonales", "#DineroInteligente", "#Shorts", "#TikTok"]
}}

REGLAS INQUEBRANTABLES:
- Exactamente 4 escenas.
- "text" de cada escena: MÁXIMO 5 palabras, en mayúsculas si es gancho. Piensa en lo que ves sobreimpreso en TikTok.
- "narration": 45-55 palabras. SIEMPRE acaba con "Te lo dice, arroba finanzas jpg."
- Cifras REALES y CONCRETAS. Nada de "mucho dinero" → di "2.400€ al año".
- stock_keywords: escenas con PERSONAS haciendo cosas reales. Nada de gráficos abstractos.
- image_prompt: cinematográfico, emocional, SIN texto en la imagen."""


class ScriptAgent:
    def generate(self, topic: str | None = None) -> dict:
        """
        Genera un guión completo para un Short.
        Usa llm_client: Claude CLI (claude -p) → fallback Ollama.

        Args:
            topic: Tema sugerido. None = el agente elige uno de su banco de temas.

        Returns:
            dict con title, description, narration, scenes[], tags[]
        """
        if topic is None:
            topic = self._pick_topic()

        prompt = SCRIPT_PROMPT_TEMPLATE.format(topic=topic)
        logger.info(f"Generando guión sobre: {topic}")

        raw = generate(SYSTEM_PROMPT, prompt)
        script = self._parse_json(raw)

        if script is None:
            raise RuntimeError("No se pudo generar el guión (respuesta no es JSON válido)")

        logger.info(f"Guión generado: '{script.get('title', 'sin título')}'")
        return script

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
            "El café diario te cuesta 1.200€ al año — qué pasaría si los invirtieras",
            "Con 50€/mes en un indexado al 7% tendrás 26.000€ en 20 años",
            "El 67% de españoles no tiene fondo de emergencia — cómo crear uno en 90 días",
            "Tu banco te cobra 200€/año en comisiones que ni sabes que existen",
            "La regla del 72: divide 72 entre el interés y sabrás cuándo se duplica tu dinero",
            "Cobras 1.500€ y crees que no puedes ahorrar — el truco de las 24 horas",
            "Un gasto de 30€/mes que no usas te roba 3.600€ en 10 años",
            "Invertir 100€/mes desde los 25 vs desde los 35 — la diferencia son 100.000€",
            "3 apps que te avisan antes de que tu cuenta baje de 500€",
            "El método bola de nieve: cómo gente normal elimina 15.000€ de deuda",
            "Por qué el 80% de los que compran acciones individuales pierden dinero",
            "Ganar 2.000€ extra al año con cosas que ya tienes en casa",
            "Tu suscripción de streaming te cuesta más que un fondo indexado mensual",
            "Qué pasa si metes 200€/mes en un depósito al 3% durante 5 años",
            "El error de los 20.000€ que cometen las parejas al comprar piso",
            "Automatiza tus ahorros el día 1 del mes y no vuelvas a pensarlo",
            "Inflación al 3% significa que tus 10.000€ valen 7.400€ en 10 años",
            "Cómo negociar tu sueldo: datos dicen que el 70% que pide aumento, lo consigue",
            "ETFs vs planes de pensiones — cuál te conviene más si tienes menos de 40",
            "5€ al día en comida fuera son 1.825€ al año — prepara batch cooking",
        ]
        return random.choice(topics)
