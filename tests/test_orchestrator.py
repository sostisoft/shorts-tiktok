"""
Tests for agents/orchestrator.py — prompt building and topic selection logic.
No GPU required. LLM calls are mocked.
"""
import json
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from agents.orchestrator import (
    VideoDecision,
    SYSTEM_PROMPT,
    TOPIC_PROMPT,
    decide,
    decide_from_topic,
)


class TestVideoDecision:
    """Tests for the VideoDecision dataclass."""

    def test_create_video_decision(self):
        """VideoDecision should hold all required fields."""
        vd = VideoDecision(
            topic="Test topic",
            hook="Hook text",
            narration="Narration text",
            narration_en="English narration",
            image_prompts=["p1", "p2", "p3", "p4"],
            style="cinematic",
            duration_target=20,
        )
        assert vd.topic == "Test topic"
        assert vd.duration_target == 20
        assert len(vd.image_prompts) == 4


class TestSystemPrompt:
    """Tests for the system prompt content."""

    def test_system_prompt_contains_spanish_data(self):
        """System prompt should contain real Spanish financial data."""
        assert "Euribor" in SYSTEM_PROMPT or "Euríbor" in SYSTEM_PROMPT
        assert "1.650" in SYSTEM_PROMPT or "2.100" in SYSTEM_PROMPT
        assert "TAE" in SYSTEM_PROMPT
        assert "IRPF" in SYSTEM_PROMPT

    def test_system_prompt_has_rules(self):
        """System prompt should contain content rules."""
        assert "REGLA 1" in SYSTEM_PROMPT
        assert "REGLA 2" in SYSTEM_PROMPT
        assert "REGLA 3" in SYSTEM_PROMPT
        assert "REGLA 4" in SYSTEM_PROMPT

    def test_system_prompt_requires_json(self):
        """System prompt should instruct JSON-only responses."""
        assert "JSON" in SYSTEM_PROMPT

    def test_system_prompt_has_closing_phrase(self):
        """System prompt should require the signature closing phrase."""
        assert "finanzas jota pe ge" in SYSTEM_PROMPT or "finanzas jpg" in SYSTEM_PROMPT


class TestDecide:
    """Tests for the decide() function (automatic topic selection)."""

    def test_decide_builds_prompt_with_recent_topics(self):
        """decide() should include recent topics in the prompt to avoid repetition."""
        recent = ["Fondo de emergencia", "Inversion en ETFs"]
        mock_response = {
            "topic": "Gastos hormiga",
            "hook": "Te gastas 150 euros al mes sin darte cuenta",
            "narration": "Test narration. Te lo dice, arroba finanzas jota pe ge.",
            "narration_en": "Test narration en. Brought to you by at finanzas j p g.",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s1", "image_prompt": "p1", "stock_keywords": "k1"},
                {"text": "s2", "image_prompt": "p2", "stock_keywords": "k2"},
                {"text": "s3", "image_prompt": "p3", "stock_keywords": "k3"},
                {"text": "s4", "image_prompt": "p4", "stock_keywords": "k4"},
            ],
            "style": "cinematic",
            "duration_target": 20,
        }

        with patch("agents.orchestrator.generate_json", return_value=mock_response) as mock_gen:
            result = decide(recent)

        assert isinstance(result, VideoDecision)
        assert result.topic == "Gastos hormiga"

        # Verify the LLM was called with recent topics in the prompt
        call_args = mock_gen.call_args
        user_msg = call_args[0][1]
        assert "Fondo de emergencia" in user_msg
        assert "Inversion en ETFs" in user_msg

    def test_decide_with_empty_recent_topics(self):
        """decide() should work when no topics have been published yet."""
        mock_response = {
            "topic": "Primer video",
            "hook": "hook",
            "narration": "narration",
            "narration_en": "narration en",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s1", "image_prompt": "p1", "stock_keywords": "k1"},
                {"text": "s2", "image_prompt": "p2", "stock_keywords": "k2"},
                {"text": "s3", "image_prompt": "p3", "stock_keywords": "k3"},
                {"text": "s4", "image_prompt": "p4", "stock_keywords": "k4"},
            ],
            "style": "modern",
            "duration_target": 20,
        }

        with patch("agents.orchestrator.generate_json", return_value=mock_response):
            result = decide([])

        assert isinstance(result, VideoDecision)

    def test_decide_includes_date_in_prompt(self):
        """decide() should include today's date in the user message."""
        mock_response = {
            "topic": "t", "hook": "h", "narration": "n", "narration_en": "ne",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
            ],
            "style": "s", "duration_target": 20,
        }

        with patch("agents.orchestrator.generate_json", return_value=mock_response) as mock_gen:
            decide([])

        user_msg = mock_gen.call_args[0][1]
        today_str = date.today().strftime("%A %d de %B de %Y")
        assert today_str in user_msg


class TestDecideFromTopic:
    """Tests for the decide_from_topic() function (user-specified topic)."""

    def test_decide_from_topic_uses_given_topic(self):
        """decide_from_topic() should pass the user's topic to the LLM."""
        mock_response = {
            "topic": "Hipoteca variable vs fija",
            "hook": "hook",
            "narration": "narration",
            "narration_en": "narration en",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s1", "image_prompt": "p1", "stock_keywords": "k1"},
                {"text": "s2", "image_prompt": "p2", "stock_keywords": "k2"},
                {"text": "s3", "image_prompt": "p3", "stock_keywords": "k3"},
                {"text": "s4", "image_prompt": "p4", "stock_keywords": "k4"},
            ],
            "style": "documentary",
            "duration_target": 20,
        }

        with patch("agents.orchestrator.generate_json", return_value=mock_response) as mock_gen:
            result = decide_from_topic("Hipoteca variable vs fija")

        assert result.topic == "Hipoteca variable vs fija"
        user_msg = mock_gen.call_args[0][1]
        assert "Hipoteca variable vs fija" in user_msg

    def test_decide_from_topic_includes_enfoque(self):
        """decide_from_topic() should include enfoque in the prompt when provided."""
        mock_response = {
            "topic": "Ahorro", "hook": "h", "narration": "n", "narration_en": "ne",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
            ],
            "style": "s", "duration_target": 20,
        }

        with patch("agents.orchestrator.generate_json", return_value=mock_response) as mock_gen:
            decide_from_topic("Ahorro", enfoque="para jovenes de 25 anos")

        user_msg = mock_gen.call_args[0][1]
        assert "para jovenes de 25 anos" in user_msg

    def test_decide_from_topic_uses_both_prompts(self):
        """decide_from_topic() should combine SYSTEM_PROMPT and TOPIC_PROMPT."""
        mock_response = {
            "topic": "t", "hook": "h", "narration": "n", "narration_en": "ne",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
            ],
            "style": "s", "duration_target": 20,
        }

        with patch("agents.orchestrator.generate_json", return_value=mock_response) as mock_gen:
            decide_from_topic("Test Topic")

        system_msg = mock_gen.call_args[0][0]
        assert "Finanzas Claras" in system_msg
        assert "TEMA CONCRETO" in system_msg

    def test_decide_from_topic_with_recent_topics(self):
        """decide_from_topic() should include recent topics to avoid repetition."""
        mock_response = {
            "topic": "t", "hook": "h", "narration": "n", "narration_en": "ne",
            "image_prompts": ["p1", "p2", "p3", "p4"],
            "scenes": [
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
                {"text": "s", "image_prompt": "p", "stock_keywords": "k"},
            ],
            "style": "s", "duration_target": 20,
        }

        recent = ["Topic A", "Topic B"]
        with patch("agents.orchestrator.generate_json", return_value=mock_response) as mock_gen:
            decide_from_topic("New Topic", recent_topics=recent)

        user_msg = mock_gen.call_args[0][1]
        assert "Topic A" in user_msg
        assert "Topic B" in user_msg
