"""
Shared fixtures for the shorts test suite.
GPU-dependent tests are marked with @pytest.mark.gpu and skipped in CI.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "gpu: mark test as requiring GPU (skip in CI)")


@pytest.fixture
def tmp_dir():
    """Provides a temporary directory that is cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="shorts_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_script():
    """Returns a sample video script dict matching the pipeline format."""
    return {
        "topic": "Fondo de emergencia en 3 meses",
        "title": "El 40% de espanoles no tiene fondo de emergencia",
        "description": "Como crear tu colchon financiero paso a paso #shorts #finanzas",
        "narration": (
            "El 40% de espanoles no aguantaria un gasto imprevisto de 1.000 euros. "
            "Abre una cuenta remunerada al 3% TAE, programa 150 euros al mes, "
            "y en 3 meses tendras tu fondo de emergencia. "
            "Te lo dice, arroba finanzas jota pe ge."
        ),
        "scenes": [
            {
                "text": "40% sin fondo emergencia",
                "image_prompt": "Close-up of empty wallet on kitchen table, dramatic lighting",
                "stock_keywords": "empty wallet money",
            },
            {
                "text": "Cuenta al 3% TAE",
                "image_prompt": "Smartphone showing banking app with savings account, modern UI",
                "stock_keywords": "smartphone banking app",
            },
            {
                "text": "150 euros al mes",
                "image_prompt": "Person putting euro bills into a glass jar, warm cozy lighting",
                "stock_keywords": "savings jar euros",
            },
            {
                "text": "Tu colchon financiero",
                "image_prompt": "Happy person checking phone with satisfied expression, bright room",
                "stock_keywords": "person happy phone",
            },
        ],
        "tags": ["#FinanzasPersonales", "#Ahorro", "#FondoEmergencia", "#Shorts"],
    }


@pytest.fixture
def sample_checkpoint_data(sample_script):
    """Returns raw checkpoint data dict for testing."""
    return {
        "job_id": "test1234",
        "title": sample_script["title"],
        "status": "running",
        "failed_phase": None,
        "created_at": "2026-03-20T10:00:00",
        "updated_at": "2026-03-20T10:00:00",
        "script": sample_script,
        "phases": {},
    }
