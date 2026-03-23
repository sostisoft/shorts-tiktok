"""
saas/providers/script/templates.py
Video template definitions — customize prompt, visual style, pacing per template.
"""

TEMPLATES = {
    "finance": {
        "name": "Finance",
        "description": "Personal finance tips with hard data and actionable advice",
        "style_instructions": "Estilo finanzas personales. Datos duros, cifras reales en euros. Tono: como un colega que sabe de pasta. Cierra con frase del canal.",
        "visual_style": "clean modern financial aesthetic, professional lighting",
        "scene_count": 4,
        "duration_seconds": 20,
        "music_mood": "corporate upbeat",
    },
    "documentary": {
        "name": "Documentary",
        "description": "Slow-paced, deep narrator voice, cinematic visuals",
        "style_instructions": "Estilo documental. Narración pausada y profunda, como un documental de Netflix. Datos históricos o poco conocidos. Genera asombro e intriga.",
        "visual_style": "cinematic dark moody lighting, documentary style, shallow depth of field",
        "scene_count": 5,
        "duration_seconds": 25,
        "music_mood": "ambient atmospheric",
    },
    "energetic": {
        "name": "Energetic",
        "description": "Fast cuts, bold text, bright colors, high energy",
        "style_instructions": "Estilo energético tipo TikTok viral. Frases CORTAS y EXPLOSIVAS. Mucha urgencia. Usa emojis en el texto de pantalla. Ritmo frenético.",
        "visual_style": "bright vibrant colors, bold graphic style, high contrast, dynamic angles",
        "scene_count": 6,
        "duration_seconds": 18,
        "music_mood": "upbeat electronic",
    },
    "educational": {
        "name": "Educational",
        "description": "Clear step-by-step explanations with infographic style",
        "style_instructions": "Estilo educativo paso a paso. Explica como un profesor excelente: claro, estructurado, con ejemplos. Numera los pasos. Usa analogías simples.",
        "visual_style": "clean infographic style, white background, clear diagrams, professional",
        "scene_count": 4,
        "duration_seconds": 20,
        "music_mood": "light background",
    },
    "listicle": {
        "name": "Listicle",
        "description": "Numbered items with snappy transitions",
        "style_instructions": "Estilo listicle: 'Top 5...', 'Las 3 mejores...'. Cada punto es una escena. Numerados. Gancho: el mejor tip va al final para retener.",
        "visual_style": "bold numbered graphics, clean modern style, colorful accents",
        "scene_count": 5,
        "duration_seconds": 20,
        "music_mood": "pop upbeat",
    },
    "storytelling": {
        "name": "Storytelling",
        "description": "Narrative arc with emotional hook and resolution",
        "style_instructions": "Estilo storytelling: cuenta una historia real o verosímil. Inicio con conflicto, desarrollo con tensión, resolución con moraleja práctica. Emocional.",
        "visual_style": "warm emotional lighting, candid photography style, intimate close-ups",
        "scene_count": 4,
        "duration_seconds": 22,
        "music_mood": "emotional piano",
    },
}


def get_template(slug: str) -> dict:
    """Get template config by slug. Falls back to 'finance' if not found."""
    return TEMPLATES.get(slug, TEMPLATES["finance"])


def get_template_names() -> list[dict]:
    """Get list of available templates with name and description."""
    return [
        {"slug": k, "name": v["name"], "description": v["description"]}
        for k, v in TEMPLATES.items()
    ]
