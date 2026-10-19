"""Bench PERFORMANCE: tempo do execute_job (solve + perfis + excel + laudo, sem extras).

Casos:
- 7 dias, 2 solutos (caso do profiling: solver ~1.5 s, extras eram ~4.7 s);
- 365 dias, série Piracicaba médio (hub piracicaba_sp, cenário medio).

Uso: python backend/scripts/bench.py
"""

import sys
import tempfile
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas import SimulateRequest, SoluteInput  # noqa: E402
from app.service import execute_job  # noqa: E402


def _two_solutes() -> list:
    return [
        SoluteInput(symbol="N", name="Nitrogênio", dose_kg_ha=60.0, kd=0.0),
        SoluteInput(symbol="K", name="Potássio", dose_kg_ha=60.0, kd=1.0),
    ]


def _bench_7d_2solute() -> float:
    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key="soja",
        total_days=7,
        rain_mm=60.0,
        solutes=_two_solutes(),
    )
    with tempfile.TemporaryDirectory(prefix="bench-7d-") as tmp:
        t0 = time.perf_counter()
        execute_job(req, tmp)
        return time.perf_counter() - t0


def _bench_365d_piracicaba_medio() -> float:
    from app.climate import build_series_rows

    rain_series, et0_series, _year = build_series_rows("piracicaba_sp", "medio")
    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key="soja",
        rain_series=[float(v) for v in rain_series],
        et0_series=[float(v) for v in et0_series],
        solutes=_two_solutes(),
    )
    with tempfile.TemporaryDirectory(prefix="bench-365d-") as tmp:
        t0 = time.perf_counter()
        execute_job(req, tmp)
        return time.perf_counter() - t0


def main() -> None:
    s7 = _bench_7d_2solute()
    print(f"7-day 2-solute execute_job: {s7:.2f} s")
    s365 = _bench_365d_piracicaba_medio()
    print(f"365-day Piracicaba medio execute_job: {s365:.2f} s")


if __name__ == "__main__":
    main()
