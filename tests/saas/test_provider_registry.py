"""
tests/test_provider_registry.py
Tests for provider registry — plan → provider mapping.
"""
import pytest

from saas.config import PlanTier
from saas.providers.registry import PHASES, get_provider


def test_starter_plan_providers():
    """Starter plan uses cheap/free providers."""
    script = get_provider(PlanTier.STARTER, "script")
    image = get_provider(PlanTier.STARTER, "image")
    video = get_provider(PlanTier.STARTER, "video")
    tts = get_provider(PlanTier.STARTER, "tts")

    assert type(script).__name__ == "ClaudeHaikuScriptProvider"
    assert type(image).__name__ == "StockImageProvider"
    assert type(video).__name__ == "KenBurnsVideoProvider"
    assert type(tts).__name__ == "EdgeTTSProvider"


def test_growth_plan_providers():
    """Growth plan upgrades images to FLUX."""
    image = get_provider(PlanTier.GROWTH, "image")
    video = get_provider(PlanTier.GROWTH, "video")

    assert type(image).__name__ == "FalFluxImageProvider"
    assert type(video).__name__ == "KenBurnsVideoProvider"  # Still Ken Burns


def test_agency_plan_providers():
    """Agency plan uses premium providers."""
    script = get_provider(PlanTier.AGENCY, "script")
    image = get_provider(PlanTier.AGENCY, "image")
    video = get_provider(PlanTier.AGENCY, "video")
    tts = get_provider(PlanTier.AGENCY, "tts")

    assert type(script).__name__ == "ClaudeSonnetScriptProvider"
    assert type(image).__name__ == "FalFluxImageProvider"
    assert type(video).__name__ == "KlingVideoProvider"
    assert type(tts).__name__ == "ElevenLabsTTSProvider"


def test_all_phases_registered():
    """Every plan has all required phases."""
    for plan in PlanTier:
        for phase in PHASES:
            provider = get_provider(plan, phase)
            assert provider is not None, f"Missing provider: {plan}/{phase}"


def test_unknown_phase_raises():
    """Unknown phase raises ValueError."""
    with pytest.raises(ValueError, match="Unknown phase"):
        get_provider(PlanTier.STARTER, "nonexistent")


def test_string_plan_works():
    """Registry accepts plan as string."""
    provider = get_provider("starter", "script")
    assert type(provider).__name__ == "ClaudeHaikuScriptProvider"
