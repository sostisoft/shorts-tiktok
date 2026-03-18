import anthropic
import json
import os
from dataclasses import dataclass
from datetime import date

@dataclass
class VideoDecision:
    topic: str              # Tema concreto del vídeo
    hook: str               # Primera frase — gancho 3 segundos
    narration: str          # Guión completo para TTS (~200 palabras)
    image_prompts: list     # 8-10 prompts en inglés para FLUX
    style: str              # Estilo visual ("cinematic office", "modern city", etc)
    duration_target: int    # Segundos objetivo (45-60)

SYSTEM_PROMPT = """
Eres el director de contenido de "Finanzas Claras", un canal de YouTube Shorts
sobre finanzas personales para españoles de 25-45 años.

El canal publica vídeos 100% generados con IA: imágenes sintéticas + narración en off.
Sin cara, sin cámara. Estilo documental moderno.

TONO: Directo, cercano, sin tecnicismos. Como un amigo que sabe de finanzas.
IDIOMA: Castellano neutro (sin modismos regionales)
DURACIÓN: 45-60 segundos

TEMAS del canal (rotar, no repetir):
- Fondos indexados y cómo empezar
- Hipoteca fija vs variable
- Plan de pensiones: sí o no
- Cómo ahorrar el 20% del sueldo
- ETFs para principiantes
- Cuenta remunerada vs fondo monetario
- Declaración de la renta: trucos legales
- Regla del 50/30/20
- Cómo salir de deudas
- Inversión inmobiliaria vs bolsa
- FIRE: jubilación anticipada
- Broker: cómo elegir
- Inflación y tu dinero
- Diversificación de cartera

FORMATO DE GANCHO (primeros 3 segundos):
- Pregunta que genera curiosidad: "¿Sabías que el 90% de los españoles pierde dinero por esto?"
- Dato impactante: "Con 200€ al mes puedes jubilarte a los 50"
- Afirmación provocadora: "Tu banco te está robando y no lo sabes"

IMAGEN PROMPTS: Escenas realistas, estilo cinematográfico.
Personas en oficinas modernas, ciudades españolas, gráficos financieros,
ordenadores con datos, vida de clase media-alta española.
SIEMPRE en inglés, muy descriptivos (50-80 palabras cada uno).

Responde ÚNICAMENTE en JSON sin backticks ni texto adicional.
"""

def decide(recent_topics: list[str]) -> VideoDecision:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_msg = f"""
Hoy es {date.today().strftime('%A %d de %B de %Y')}.

Temas publicados recientemente (NO repetir):
{json.dumps(recent_topics, ensure_ascii=False)}

Decide el siguiente vídeo para Finanzas Claras.

Responde con este JSON exacto:
{{
  "topic": "título descriptivo del tema",
  "hook": "primera frase gancho (máx 15 palabras)",
  "narration": "guión completo de 45-60 segundos de lectura en castellano",
  "image_prompts": [
    "prompt 1 en inglés, muy descriptivo, estilo cinematográfico...",
    "prompt 2...",
    "... hasta 8 prompts"
  ],
  "style": "descripción del estilo visual general",
  "duration_target": 55
}}
"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )

    raw = msg.content[0].text.strip()
    data = json.loads(raw)
    return VideoDecision(**data)
