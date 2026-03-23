"""
tests/test_schemas.py
Tests for Pydantic schemas validation.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from saas.schemas.video import VideoCreate, VideoResponse
from saas.schemas.channel import ChannelCreate
from saas.schemas.webhook import WebhookCreate
from saas.schemas.common import APIEnvelope


def test_video_create_defaults():
    """VideoCreate has sensible defaults."""
    v = VideoCreate()
    assert v.topic is None
    assert v.style == "finance"
    assert v.auto_publish is False


def test_video_create_with_topic():
    v = VideoCreate(topic="Ahorro para principiantes")
    assert v.topic == "Ahorro para principiantes"


def test_channel_create_validation():
    """ChannelCreate requires platform and credentials."""
    c = ChannelCreate(
        platform="youtube",
        display_name="My Channel",
        credentials={"token": "abc"},
    )
    assert c.platform == "youtube"


def test_webhook_create_validates_url():
    """WebhookCreate validates URL format."""
    w = WebhookCreate(
        url="https://example.com/webhook",
        events=["video.completed"],
    )
    assert str(w.url) == "https://example.com/webhook"


def test_webhook_invalid_url():
    """Invalid URL raises validation error."""
    with pytest.raises(ValidationError):
        WebhookCreate(url="not-a-url", events=["video.completed"])


def test_api_envelope():
    """APIEnvelope wraps data correctly."""
    envelope = APIEnvelope(data={"test": True})
    assert envelope.success is True
    assert envelope.data == {"test": True}
    assert envelope.error is None
