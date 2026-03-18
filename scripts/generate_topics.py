"""
Genera 1000 ideas de vídeo con Claude y las inserta en la BD.
Se ejecuta en lotes de 50 para no superar el límite de tokens.
"""
import json
import os
import sys
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from db.models import init_db, Session, TopicIdea

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("topics")

BATCH_SIZE = 20
TOTAL_TARGET = 1000

SYSTEM = """Eres un experto en contenido viral de finanzas personales para público español (25-45 años).
Canal: "Finanzas Claras" — tono cercano, práctico, sin tecnicismos innecesarios.

REGLAS:
- Cada tema debe ser ÚNICO — nunca repetir el mismo concepto con diferente redacción
- Cubrir TODAS las categorías: ahorro, inversión, deuda, impuestos España, hipotecas, seguros, jubilación, emprendimiento, cripto, inmobiliario, presupuesto, inflación, nóminas, autónomos, herencias, IRPF, IVA, Seguridad Social, tarjetas, bancos, fondos indexados, ETFs, planes de pensiones, etc.
- Mezclar: tips prácticos, errores comunes, datos sorprendentes, comparativas, mitos, noticias económicas atemporales
- Prioridad "alta" = temas con alto potencial viral (polémicos, sorprendentes, de actualidad permanente)
- Prioridad "normal" = temas educativos sólidos
- Prioridad "baja" = temas de nicho o muy específicos
- Los hashtags deben ser los que mejor funcionan en el algoritmo para finanzas en español
- El texto es el guión del vídeo (máximo 40 palabras, ~15 segundos hablados)
- El título debe tener máximo 60 caracteres y empezar con un emoji de finanzas (💰💸📈🏦💡🔥⚠️)

FORMATO: Devuelve SOLO un JSON array válido, sin markdown, sin explicaciones, sin ```json.
Cada elemento:
[
  {
    "tema": "concepto principal del vídeo",
    "enfoque": "ángulo específico o gancho",
    "titulo": "💰 Título corto para redes (max 60 chars)",
    "texto": "Guión del vídeo de 40 palabras máximo. Empieza con un gancho fuerte. Termina con CTA.",
    "hashtags": "#finanzas #dinero #ahorro #inversión #españa (5-8 relevantes)",
    "prioridad": "alta|normal|baja"
  }
]"""


def get_existing_topics() -> list[str]:
    """Devuelve todos los temas ya en la BD para no repetir."""
    with Session() as s:
        rows = s.query(TopicIdea.tema).all()
        return [r.tema for r in rows]


def generate_batch(client, batch_num: int, existing: list[str]) -> list[dict]:
    """Genera un lote de BATCH_SIZE ideas."""

    # Categorías rotativas para asegurar diversidad
    categories = [
        "ahorro y presupuesto", "inversión y bolsa", "deuda y tarjetas",
        "impuestos España (IRPF, IVA)", "hipotecas", "seguros",
        "jubilación y pensiones", "emprendimiento y autónomos",
        "cripto y nuevas inversiones", "inmobiliario",
        "nóminas y Seguridad Social", "herencias e impuestos",
        "fondos indexados y ETFs", "bancos y cuentas",
        "inflación y economía", "errores financieros",
        "mitos del dinero", "comparativas financieras",
        "trucos legales fiscales", "finanzas para jóvenes",
    ]

    category_focus = categories[batch_num % len(categories)]

    # Muestra de temas existentes para evitar duplicados
    existing_sample = existing[-100:] if len(existing) > 100 else existing

    user_msg = f"""Genera exactamente {BATCH_SIZE} ideas de vídeos de 15 segundos.

Lote {batch_num + 1} — enfocado especialmente en: {category_focus}
(pero incluye variedad de otras categorías también)

TEMAS YA GENERADOS (NO REPETIR ni reformular):
{json.dumps(existing_sample, ensure_ascii=False)}

Total de temas existentes: {len(existing)}

Genera {BATCH_SIZE} ideas NUEVAS y ÚNICAS. Solo JSON array puro."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = msg.content[0].text.strip()

    # Limpiar posible markdown
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]

    # Intentar parsear directo
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON truncado — cortar el último elemento incompleto y cerrar el array
        last_complete = raw.rfind("}")
        if last_complete > 0:
            truncated = raw[:last_complete + 1] + "\n]"
            return json.loads(truncated)
        raise


def insert_batch(ideas: list[dict]) -> int:
    """Inserta ideas en la BD. Devuelve cuántas se insertaron."""
    count = 0
    with Session() as s:
        for idea in ideas:
            # Verificar que no existe ya
            exists = s.query(TopicIdea).filter_by(tema=idea["tema"]).first()
            if exists:
                continue

            t = TopicIdea(
                tema=idea["tema"],
                enfoque=idea.get("enfoque", ""),
                titulo=idea.get("titulo", ""),
                texto=idea.get("texto", ""),
                hashtags=idea.get("hashtags", ""),
                prioridad=idea.get("prioridad", "normal"),
                estado="pendiente",
            )
            s.add(t)
            count += 1
        s.commit()
    return count


def main():
    init_db()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    existing = get_existing_topics()
    logger.info(f"Temas existentes en BD: {len(existing)}")

    total_inserted = 0
    batch_num = 0

    while len(existing) < TOTAL_TARGET:
        remaining = TOTAL_TARGET - len(existing)
        logger.info(f"Lote {batch_num + 1} — faltan {remaining} temas...")

        try:
            ideas = generate_batch(client, batch_num, existing)
            inserted = insert_batch(ideas)
            total_inserted += inserted

            # Actualizar lista de existentes
            new_topics = [i["tema"] for i in ideas]
            existing.extend(new_topics)

            logger.info(f"  Generados: {len(ideas)}, Insertados: {inserted}, Total: {len(existing)}")

        except Exception as e:
            logger.error(f"  Error en lote {batch_num + 1}: {e}")
            time.sleep(5)

        batch_num += 1
        time.sleep(1)  # Rate limit

    logger.info(f"Completado. {total_inserted} temas insertados. Total en BD: {len(existing)}")


if __name__ == "__main__":
    main()
