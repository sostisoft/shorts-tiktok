import json
from dataclasses import dataclass
from datetime import date
from agents.llm_client import generate_json


@dataclass
class VideoDecision:
    topic: str              # Tema concreto del vídeo (único, nunca repetido)
    hook: str               # Primera frase — gancho 2 segundos (castellano)
    narration: str          # Guión castellano para TTS (~50 palabras, 20s)
    narration_en: str       # Guión inglés para TTS (~50 palabras, 20s)
    image_prompts: list     # 4 prompts en inglés para FLUX
    style: str              # Estilo visual ("cinematic office", "modern city", etc)
    duration_target: int    # Segundos objetivo (20)

SYSTEM_PROMPT = """
Eres el director de contenido de "Finanzas Claras", un canal de YouTube Shorts
sobre finanzas personales para españoles de 25-45 años.

El canal publica vídeos 100% generados con IA: imágenes sintéticas + narración en off.
Sin cara, sin cámara. Estilo documental moderno.

═══════════════════════════════════════════════════════════
DATOS REALES DE ESPAÑA (2025-2026) — USA ESTOS NÚMEROS
═══════════════════════════════════════════════════════════

Salarios y coste de vida:
- Salario medio España: ~2.100€/mes brutos, ~1.650€ netos
- Gasto hormiga medio español: 120-150€/mes (cafés, suscripciones, delivery)
- El 40% de españoles no tiene fondo de emergencia
- Inflación actual: ~2,8%

Hipotecas y Euríbor:
- Euríbor actual: ~2,5% (bajando desde 4,2% en 2023)
- Hipoteca media España: ~170.000€ a 25 años
- Cuota hipotecaria típica variable: ~650-750€/mes

Ahorro e inversión:
- Depósitos bancarios mejores: ~2,5-3% TAE
- Cuentas remuneradas top: ~3% TAE (Trade Republic, Revolut)
- Plan de pensiones: desgrava hasta 1.500€/año en IRPF
- Rentabilidad media S&P 500 histórica: 10,5% anual
- MSCI World últimos 30 años: ~8% anual
- Regla del 72: divide 72 entre el % de interés = años para doblar tu dinero
- Interés compuesto real: 200€/mes al 8% = 35.000€ en 10 años, 118.000€ en 20 años
- ETFs populares en España: Vanguard FTSE All-World (VWCE), iShares MSCI World
- Brokers más usados: MyInvestor, Indexa Capital, Trade Republic

Autónomos:
- Cuota autónomo mínima: ~230€/mes, máxima: ~530€/mes

Deudas:
- Efecto bola de nieve: pagar primero la deuda con mayor tipo de interés

═══════════════════════════════════════════════════════════
REGLAS DE CONTENIDO — OBLIGATORIAS
═══════════════════════════════════════════════════════════

REGLA 1 — SIEMPRE datos reales de España:
Cada guión DEBE incluir al menos 2 cifras REALES de la tabla anterior.
NUNCA inventes porcentajes ni cifras. NUNCA redondees a números bonitos.
Usa siempre euros (€), no dólares. Usa TAE, Euríbor, IRPF — terminología española.

REGLA 2 — Formato "Si haces X → en Y tiempo → tendrás Z€":
El consejo central SIEMPRE debe seguir este patrón con números concretos.
  MAL:  "Invierte pronto y verás resultados"
  MAL:  "Ahorra un poco cada mes y tu futuro cambiará"
  BIEN: "Mete 200€ al mes en un fondo indexado al 8% y en 20 años tendrás 118.000€"
  BIEN: "Pon 150€/mes en una cuenta al 3% TAE y en 1 año tienes 1.827€ de fondo de emergencia"

REGLA 3 — UN consejo accionable que puedas hacer HOY:
El espectador debe poder actuar en los próximos 5 minutos tras ver el vídeo.
  MAL:  "Diversifica tu cartera" (vago, no sabe por dónde empezar)
  BIEN: "Abre una cuenta en MyInvestor, elige el plan indexado, y programa 100€ al mes"
  BIEN: "Entra en tu banco online, cancela las 3 suscripciones que no usas, y ahorra 40€ este mes"

REGLA 4 — El gancho (hook) DEBE tener una estadística IMPACTANTE o un hecho contraintuitivo:
El gancho es lo que para el scroll. Debe provocar una reacción visceral.
  MAL:  "¿Quieres mejorar tus finanzas?"
  MAL:  "Hoy te cuento un truco de ahorro"
  BIEN: "El 40% de españoles no aguantaría un gasto imprevisto de 1.000€"
  BIEN: "Te gastas 1.800€ al año en cafés y suscripciones sin darte cuenta"
  BIEN: "Con el Euríbor al 2,5%, tu vecino paga 200€ menos de hipoteca que hace un año"
  BIEN: "Si hubieras metido 200€ al mes hace 10 años, hoy tendrías 35.000€"

═══════════════════════════════════════════════════════════
TONO E IDIOMA
═══════════════════════════════════════════════════════════

TONO: Directo, con autoridad, como un mentor financiero que te habla claro en un bar.
Nada de frases motivacionales. Nada de "empieza tu camino". Solo datos y acción.
IDIOMA: Castellano de España (no latinoamericano). Vocabulario natural:
  "nómina" no "sueldo", "cuenta remunerada" no "cuenta de alto rendimiento",
  "hipoteca" no "préstamo de casa", "Hacienda" no "el gobierno",
  "indexado" no "fondo índice", "desgrava" no "deduce impuestos".

═══════════════════════════════════════════════════════════
REGLA CRÍTICA — NO REPETIR
═══════════════════════════════════════════════════════════

Se te dará una lista de TODOS los temas ya publicados.
NUNCA repitas un tema, ni un ángulo similar, ni una reformulación del mismo concepto.
Busca siempre un ángulo NUEVO y ESPECÍFICO.

═══════════════════════════════════════════════════════════
ESTRUCTURA DEL GUIÓN — 55-65 PALABRAS, 20 SEGUNDOS
═══════════════════════════════════════════════════════════

GANCHO (3s): Estadística impactante o hecho contraintuitivo con número real.
  Debe provocar "¿en serio?" o "no me jodas" en el espectador.

CONSEJO (14s): Acción concreta paso a paso + razón + resultado con números reales.
  Formato obligatorio: "Haz esto → porque pasa esto → y en X tiempo tendrás Y€."
  Nombra herramientas reales (MyInvestor, Trade Republic, Indexa Capital, VWCE).
  Incluye euros, porcentajes, plazos concretos. NUNCA cifras vagas.

CIERRE (3s): SIEMPRE terminar literalmente con:
  "Te lo dice, arroba finanzas jota pe ge."
  (Escribe "jota pe ge" en letras, NO "jpg" — es para TTS.)

═══════════════════════════════════════════════════════════
IMAGEN PROMPTS Y STOCK KEYWORDS
═══════════════════════════════════════════════════════════

IMAGE PROMPTS: 4 escenas realistas, estilo cinematográfico, SIEMPRE en inglés.
Muy descriptivos (50-80 palabras cada uno). Visualmente distintas entre sí.
Escena 1 = gancho visual impactante. Escenas 2-3 = desarrollo. Escena 4 = cierre.

STOCK KEYWORDS: Campo "stock_keywords" con 2-3 palabras clave inglés por escena.
Concretas y buscables: "person counting euros", "savings jar coins", "smartphone banking app".
NUNCA conceptos abstractos ("financial freedom") — solo escenas reales filmables.

═══════════════════════════════════════════════════════════
RESPUESTA
═══════════════════════════════════════════════════════════

Responde ÚNICAMENTE en JSON válido. Sin backticks, sin texto adicional, sin explicaciones.
"""

TOPIC_PROMPT = """
Se te da un TEMA CONCRETO elegido por el creador del canal.
Tu trabajo es SOLO generar el guión, gancho e image prompts para ese tema.
NO elijas otro tema. Trabaja exclusivamente con el que se te da.

IMPORTANTE: Aunque el tema esté definido, DEBES seguir TODAS las reglas del sistema:
- Usa datos REALES de España de la tabla (euros, TAE, Euríbor, etc.)
- El gancho DEBE tener una estadística impactante o hecho contraintuitivo
- Formato obligatorio: "Si haces X → en Y tiempo → tendrás Z€"
- Da UN consejo accionable que se pueda hacer HOY (nombra apps, brokers, pasos concretos)
- 55-65 palabras, SIEMPRE termina con "Te lo dice, arroba finanzas jota pe ge."

Responde ÚNICAMENTE en JSON válido. Sin backticks, sin texto adicional.
"""


def decide(recent_topics: list[str]) -> VideoDecision:
    """LLM elige tema libremente (modo automático)."""
    user_msg = f"""
Hoy es {date.today().strftime('%A %d de %B de %Y')}.

TEMAS YA PUBLICADOS — PROHIBIDO repetir ni reformular:
{json.dumps(recent_topics, ensure_ascii=False) if recent_topics else '["(ninguno todavía)"]'}

Genera el siguiente vídeo. Recuerda:
1. GANCHO: Estadística REAL impactante de España (número concreto que pare el scroll)
2. CONSEJO: "Si haces X → en Y tiempo → tendrás Z€" con datos reales de la tabla
3. ACCIÓN HOY: Nombra una app, broker o paso concreto que pueda hacer en 5 minutos
4. EXACTAMENTE 55-65 palabras castellano España, 20 segundos
5. TERMINA con "Te lo dice, arroba finanzas jota pe ge." (SIEMPRE, literal)
6. Versión inglés termina con "Brought to you by at finanzas j p g."
7. Usa datos de la tabla: Euríbor 2,5%, salario 1.650€ netos, inflación 2,8%, MSCI World 8%, etc.

JSON exacto:
{{
  "topic": "título descriptivo ÚNICO y específico",
  "hook": "frase gancho con estadística real (máx 10 palabras)",
  "narration": "guión 55-65 palabras CASTELLANO España con datos reales, termina con 'Te lo dice, arroba finanzas jota pe ge.'",
  "narration_en": "script 55-65 words American English with real data, ends with 'Brought to you by at finanzas j p g.'",
  "image_prompts": ["prompt 1", "prompt 2", "prompt 3", "prompt 4"],
  "scenes": [
    {{"text": "Frase pantalla impacto (max 6 palabras)", "image_prompt": "prompt inglés cinematográfico 50-80 palabras", "stock_keywords": "2-3 keywords buscables en Pexels"}},
    {{"text": "Frase pantalla 2", "image_prompt": "prompt 2", "stock_keywords": "keywords concretas"}},
    {{"text": "Frase pantalla 3", "image_prompt": "prompt 3", "stock_keywords": "keywords concretas"}},
    {{"text": "Frase pantalla 4", "image_prompt": "prompt 4", "stock_keywords": "keywords concretas"}}
  ],
  "style": "estilo visual coherente con el tema",
  "duration_target": 20
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

Genera guión + prompts para EXACTAMENTE este tema. Recuerda:
1. GANCHO: Estadística REAL impactante de España relacionada con este tema (número concreto)
2. CONSEJO: "Si haces X → en Y tiempo → tendrás Z€" con datos reales de la tabla del sistema
3. ACCIÓN HOY: Un paso concreto que el espectador pueda hacer en 5 minutos
4. EXACTAMENTE 55-65 palabras castellano España, 20 segundos
5. TERMINA con "Te lo dice, arroba finanzas jota pe ge." (SIEMPRE, literal, con "jota pe ge" en letras)
6. Versión inglés termina con "Brought to you by at finanzas j p g."
7. Usa datos reales: Euríbor 2,5%, salario 1.650€ netos, inflación 2,8%, MSCI World 8%, etc.

JSON exacto:
{{
  "topic": "{topic}",
  "hook": "frase gancho con estadística real (máx 10 palabras)",
  "narration": "guión 55-65 palabras CASTELLANO España con datos reales, termina con 'Te lo dice, arroba finanzas jota pe ge.'",
  "narration_en": "script 55-65 words American English with real data, ends with 'Brought to you by at finanzas j p g.'",
  "image_prompts": ["prompt 1", "prompt 2", "prompt 3", "prompt 4"],
  "scenes": [
    {{"text": "Frase pantalla impacto (max 6 palabras)", "image_prompt": "prompt inglés cinematográfico 50-80 palabras", "stock_keywords": "2-3 keywords buscables en Pexels"}},
    {{"text": "Frase pantalla 2", "image_prompt": "prompt 2", "stock_keywords": "keywords concretas"}},
    {{"text": "Frase pantalla 3", "image_prompt": "prompt 3", "stock_keywords": "keywords concretas"}},
    {{"text": "Frase pantalla 4", "image_prompt": "prompt 4", "stock_keywords": "keywords concretas"}}
  ],
  "style": "estilo visual coherente con el tema",
  "duration_target": 20
}}
"""
    data = generate_json(SYSTEM_PROMPT + "\n" + TOPIC_PROMPT, user_msg)
    return VideoDecision(**data)
