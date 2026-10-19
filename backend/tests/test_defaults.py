"""Testes dos valores padrão compartilhados entre o wizard e o schema."""

import re
from pathlib import Path

from app.schemas import SimulateRequest, SoluteInput

PAGE_TSX = Path(__file__).resolve().parents[2] / "frontend" / "app" / "page.tsx"


def test_simulate_request_defaults_match_gradio() -> None:
    request = SimulateRequest(
        soil_key="latossolo_medio",
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30, kd=0.45)],
    )

    assert request.total_days == 7
    assert request.rain_mm == 60
    assert request.initial_moisture_pct == 80
    assert request.et0_mm_day == 4.0
    assert request.depth_cm == 200


def test_frontend_initial_states_match_defaults() -> None:
    source = PAGE_TSX.read_text(encoding="utf-8")
    expected = {"days": "7", "rainMm": "60", "moisture": "80", "et0": "4"}

    for variable, value in expected.items():
        pattern = rf'const\s+\[\s*{variable}\s*,\s*\w+\s*\]\s*=\s*useState\("([^"]*)"\)'
        match = re.search(pattern, source)
        assert match is not None, f"useState de {variable} não encontrado"
        assert match.group(1) == value
