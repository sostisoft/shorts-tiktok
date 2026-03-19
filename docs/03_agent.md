# 03 — Agente de Generacion de Guiones

## Que hace

El **ScriptAgent** genera guiones completos en formato JSON para YouTube Shorts del canal "Finanzas Claras". Cada guion incluye titulo, descripcion SEO, narracion, 5 escenas con textos en pantalla, prompts de imagen para FLUX y tags de YouTube.

El sistema tiene dos capas:

- **`script_agent.py`** — agente original autocontenido (usa `requests` directo contra Ollama).
- **`llm_client.py`** — cliente LLM unificado usado por el orquestador y metadata. Mas limpio, usa `urllib` sin dependencias externas.

Ambos siguen la misma estrategia: **Ollama local primero, Claude API como fallback**.

---

## Flujo de decision

```
ScriptAgent.generate(topic=None)
    │
    ├─ topic es None → _pick_topic() elige tema aleatorio del banco interno
    │
    ├─ _try_ollama(prompt)
    │     ├─ POST a OLLAMA_URL/api/generate
    │     ├─ Modelo: qwen2.5:14b (configurable)
    │     ├─ temperature: 0.7, num_predict: 1024
    │     ├─ timeout: 120s
    │     └─ Exito → _parse_json() → devuelve dict
    │
    └─ Si Ollama falla → _try_claude(prompt)
          ├─ Usa anthropic SDK (import lazy)
          ├─ Modelo: claude-sonnet-4-20250514
          ├─ max_tokens: 1024
          ├─ system prompt separado
          └─ Exito → _parse_json() → devuelve dict

    Si ambos fallan → RuntimeError
```

La funcion `_parse_json()` es robusta: elimina bloques markdown (` ```json ... ``` `), busca el primer `{` y ultimo `}`, parsea con `json.loads` y valida que existan los campos obligatorios (`title`, `narration`, `scenes`).

---

## Cliente LLM unificado (`llm_client.py`)

El modulo `agents/llm_client.py` proporciona dos funciones que usa el resto del pipeline (orquestador, metadata):

### `generate(system, user, max_tokens=1500) -> str`

Genera texto plano. Flujo:

1. Intenta `_ollama_generate()` via `OLLAMA_HOST/api/chat` (endpoint chat, no generate).
2. Si falla y existe `ANTHROPIC_API_KEY` en el entorno, usa `_claude_generate()`.
3. Si ambos fallan, lanza `RuntimeError`.

Diferencias con ScriptAgent:
- Usa `/api/chat` (mensajes system+user separados) en vez de `/api/generate`.
- Pasa `"format": "json"` a Ollama para forzar salida JSON nativa.
- Usa `urllib.request` (stdlib) en vez de `requests`.
- `num_predict: 2000` (mas tokens que ScriptAgent).

### `generate_json(system, user, max_tokens=1500) -> dict`

Wrapper sobre `generate()` que limpia la respuesta con `_clean_json()` y la parsea a dict. Es la funcion que usan `orchestrator.py` y `metadata_gen.py`.

---

## Formato JSON de salida (ejemplo real)

Capturado ejecutando `ScriptAgent().generate()` contra Ollama con Qwen 2.5 14B:

```json
{
  "title": "La regla del 50-30-20 en accion",
  "description": "Descubre como dividir tu dinero con la regla del 50-30-20 para finanzas saludables y objetivos claros. #FinanzasPersonales #DineroInteligente #Shorts",
  "narration": "La regla del 50-30-20 es tu mejor amiga en la gestion financiera. Aprende a priorizar tus gastos, ahorrar y disfrutar.",
  "scenes": [
    {
      "text": "Necesidades basicas",
      "image_prompt": "Modern office desk with coffee and notebook, close-up shot, subtle lighting, shallow depth of field"
    },
    {
      "text": "Deseos personales",
      "image_prompt": "Young professional woman smiling at laptop screen while reviewing finances, vibrant colors, dynamic composition, vertical portrait"
    },
    {
      "text": "Guarda para el futuro",
      "image_prompt": "Stack of coins growing into a pile of bills in front of a calculator and notebook on wooden desk, cinematic lighting, shallow depth of field"
    },
    {
      "text": "Objetivos claros",
      "image_prompt": "Person looking at the horizon with briefcase, golden hour light, soft shadows, vertical composition, financial freedom concept"
    },
    {
      "text": "A por ello!",
      "image_prompt": "Hands pushing open door to a bright future, sunrise behind, dynamic lighting, shallow depth of field, vertical frame"
    }
  ],
  "tags": [
    "#FinanzasPersonales",
    "#DineroInteligente",
    "#Shorts"
  ]
}
```

### Campos

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `title` | `str` | Titulo gancho para YouTube (max 60 chars) |
| `description` | `str` | Descripcion SEO con hashtags (max 200 chars) |
| `narration` | `str` | Texto completo para TTS, max 60 palabras |
| `scenes` | `list[dict]` | 5 escenas, cada una con `text` (overlay) e `image_prompt` (FLUX) |
| `tags` | `list[str]` | Hashtags de YouTube |

---

## Configuracion (variables de entorno / `.env`)

```bash
# Ollama local (ScriptAgent usa OLLAMA_URL, llm_client usa OLLAMA_HOST)
OLLAMA_URL=http://localhost:11434     # Para script_agent.py
OLLAMA_HOST=http://localhost:11434    # Para llm_client.py (orquestador, metadata)
OLLAMA_MODEL=qwen2.5:14b             # Modelo Ollama (ambos modulos)

# Fallback a Claude API (opcional)
ANTHROPIC_API_KEY=sk-ant-...          # Si no existe, el fallback no se activa
```

**Nota:** Existen dos variables para la URL de Ollama (`OLLAMA_URL` y `OLLAMA_HOST`) porque `script_agent.py` y `llm_client.py` se escribieron en momentos distintos. Ambas apuntan al mismo servidor. En produccion se configuran las dos en `.env`.

---

## Banco de temas de finanzas

`ScriptAgent._pick_topic()` selecciona aleatoriamente de 15 temas predefinidos:

1. Como ahorrar el 20% de tu sueldo automaticamente
2. El error que cometen el 90% de los que invierten por primera vez
3. Regla del 50-30-20 para gestionar tu dinero
4. Por que el interes compuesto te hace rico (o pobre)
5. 3 gastos que debes eliminar para mejorar tus finanzas
6. La diferencia entre activos y pasivos que nadie te ensena
7. Como crear un fondo de emergencia en 3 meses
8. Inversion en fondos indexados para principiantes
9. Como negociar un aumento de sueldo con exito
10. El secreto de las personas que alcanzan la libertad financiera
11. Por que deberias tener multiples fuentes de ingreso
12. Como eliminar deudas con el metodo bola de nieve
13. ETF vs acciones individuales: que te conviene mas
14. El coste oculto de no invertir tus ahorros
15. Automatiza tus finanzas y deja de preocuparte por el dinero

El orquestador (`orchestrator.py`) no usa este banco — el LLM elige libremente evitando temas ya publicados.

---

## Orquestador (`orchestrator.py`)

El orquestador es la evolucion del ScriptAgent. Usa `llm_client.generate_json()` y produce un `VideoDecision` mas completo:

### `VideoDecision` (dataclass)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `topic` | `str` | Tema unico, nunca repetido |
| `hook` | `str` | Frase gancho de 2 segundos (max 8 palabras) |
| `narration` | `str` | Guion en castellano (~40 palabras, 15s) |
| `narration_en` | `str` | Guion en ingles (~40 palabras, 15s) |
| `image_prompts` | `list` | 3 prompts en ingles para FLUX (50-80 palabras c/u) |
| `style` | `str` | Estilo visual ("cinematic office", "modern city", etc) |
| `duration_target` | `int` | Segundos objetivo (siempre 15) |

### Funciones

- **`decide(recent_topics)`** — Modo automatico. El LLM elige tema libremente, recibe la lista de temas ya publicados para no repetir. Genera guion bilingue (castellano + ingles).
- **`decide_from_topic(topic, enfoque, recent_topics)`** — Modo manual. Se le da un tema concreto y el LLM genera el guion para ese tema exacto. Util para videos tematicos o de actualidad.

Ambas funciones devuelven un `VideoDecision` listo para el pipeline de generacion.

---

## Generador de metadata (`metadata_gen.py`)

Genera titulo SEO, descripcion y tags optimizados para YouTube a partir del guion ya generado.

### `VideoMetadata` (dataclass)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `title` | `str` | Max 60 chars, empieza con emoji financiero |
| `description` | `str` | Gancho + keywords + hashtags + CTA |
| `tags` | `list` | 10-15 tags del nicho |

### Funciones

- **`generate(topic, hook, narration)`** — Metadata en espanol.
- **`generate_en(topic, hook, narration_en)`** — Metadata en ingles.

Ambas usan `llm_client.generate_json()` con prompts SEO especializados.

---

## Probar el agente en standalone

### ScriptAgent (guion basico)

```bash
cd /home/gmktec/shorts
source venv/bin/activate

# Con tema aleatorio
python -c "
from agents.script_agent import ScriptAgent
import json
s = ScriptAgent()
result = s.generate()
print(json.dumps(result, indent=2, ensure_ascii=False))
"

# Con tema especifico
python -c "
from agents.script_agent import ScriptAgent
import json
s = ScriptAgent()
result = s.generate(topic='Como crear un fondo de emergencia')
print(json.dumps(result, indent=2, ensure_ascii=False))
"
```

### Orquestador (VideoDecision completo)

```bash
python -c "
from agents.orchestrator import decide, decide_from_topic
print(decide(recent_topics=[]))
"

# Con tema manual
python -c "
from agents.orchestrator import decide_from_topic
d = decide_from_topic('Interes compuesto', enfoque='ejemplo practico')
print(d)
"
```

### Metadata

```bash
python -c "
from agents.metadata_gen import generate
m = generate('Regla 50-30-20', 'Sabes dividir tu dinero?', 'La regla del 50-30-20...')
print(m)
"
```

### llm_client directo

```bash
python -c "
from agents.llm_client import generate, generate_json
# Texto plano
print(generate('Eres experto en finanzas', 'Dame un consejo de ahorro en 1 frase'))
# JSON
print(generate_json('Responde en JSON', 'Dame {\"consejo\": \"...\"}'))
"
```

---

## Archivos relevantes

| Archivo | Funcion |
|---------|---------|
| `agents/script_agent.py` | Agente original de guiones (autocontenido) |
| `agents/llm_client.py` | Cliente LLM unificado (Ollama + Claude fallback) |
| `agents/orchestrator.py` | Orquestador con VideoDecision bilingue |
| `agents/metadata_gen.py` | Generador de metadata SEO para YouTube |
