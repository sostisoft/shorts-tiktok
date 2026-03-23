"""
saas/providers/registry.py
Maps (plan, phase) -> concrete provider class.
Central configuration for which providers each plan uses.
"""
from saas.config import PlanTier
from saas.providers.base import (
    ComposeProvider,
    ImageProvider,
    MusicProvider,
    PublishProvider,
    ScriptProvider,
    TTSProvider,
    VideoProvider,
)


def _lazy_import(module_path: str, class_name: str):
    """Lazy import to avoid circular imports and heavy module loading."""
    def factory():
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)()
    return factory


# Trial uses same providers as Starter
_STARTER_PROVIDERS = {
    "script": _lazy_import("saas.providers.script.claude_api", "ClaudeHaikuScriptProvider"),
    "image": _lazy_import("saas.providers.image.stock_image", "StockImageProvider"),
    "video": _lazy_import("saas.providers.video.kenburns", "KenBurnsVideoProvider"),
    "tts": _lazy_import("saas.providers.tts.edge_tts", "EdgeTTSProvider"),
    "music": _lazy_import("saas.providers.music.tracks", "TracksProvider"),
    "compose": _lazy_import("saas.providers.compose.ffmpeg", "FFmpegComposeProvider"),
}

# Provider registry: plan -> phase -> lazy factory
_REGISTRY: dict[PlanTier, dict[str, callable]] = {
    PlanTier.TRIAL: _STARTER_PROVIDERS,
    PlanTier.STARTER: {
        "script": _lazy_import("saas.providers.script.claude_api", "ClaudeHaikuScriptProvider"),
        "image": _lazy_import("saas.providers.image.stock_image", "StockImageProvider"),
        "video": _lazy_import("saas.providers.video.kenburns", "KenBurnsVideoProvider"),
        "tts": _lazy_import("saas.providers.tts.edge_tts", "EdgeTTSProvider"),
        "music": _lazy_import("saas.providers.music.tracks", "TracksProvider"),
        "compose": _lazy_import("saas.providers.compose.ffmpeg", "FFmpegComposeProvider"),
    },
    PlanTier.GROWTH: {
        "script": _lazy_import("saas.providers.script.claude_api", "ClaudeHaikuScriptProvider"),
        "image": _lazy_import("saas.providers.image.fal_flux", "FalFluxImageProvider"),
        "video": _lazy_import("saas.providers.video.kenburns", "KenBurnsVideoProvider"),
        "tts": _lazy_import("saas.providers.tts.edge_tts", "EdgeTTSProvider"),
        "music": _lazy_import("saas.providers.music.tracks", "TracksProvider"),
        "compose": _lazy_import("saas.providers.compose.ffmpeg", "FFmpegComposeProvider"),
    },
    PlanTier.AGENCY: {
        "script": _lazy_import("saas.providers.script.claude_api", "ClaudeSonnetScriptProvider"),
        "image": _lazy_import("saas.providers.image.fal_flux", "FalFluxImageProvider"),
        "video": _lazy_import("saas.providers.video.kling", "KlingVideoProvider"),
        "tts": _lazy_import("saas.providers.tts.elevenlabs", "ElevenLabsTTSProvider"),
        "music": _lazy_import("saas.providers.music.tracks", "TracksProvider"),
        "compose": _lazy_import("saas.providers.compose.ffmpeg", "FFmpegComposeProvider"),
    },
}

PHASES = ("script", "image", "video", "tts", "music", "compose")


def get_provider(plan: PlanTier | str, phase: str):
    """Get a provider instance for a given plan and phase."""
    if isinstance(plan, str):
        plan = PlanTier(plan)
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}. Must be one of {PHASES}")
    if plan not in _REGISTRY:
        raise ValueError(f"Unknown plan: {plan}")
    factory = _REGISTRY[plan][phase]
    return factory()
