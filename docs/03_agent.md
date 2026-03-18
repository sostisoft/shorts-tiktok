# 03 — Agente Claude: orquestador y metadata

## agents/orchestrator.py

```python
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
...
"""

def decide(recent_topics: list[str]) -> VideoDecision:
    ...
```

## agents/metadata_gen.py

```python
def generate(topic: str, hook: str, narration: str) -> VideoMetadata:
    ...
```

Ver código completo en los ficheros fuente.
