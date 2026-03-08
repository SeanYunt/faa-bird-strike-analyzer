"""Tests for PDF dossier generation."""

import pytest
from pathlib import Path

from reports.pdf import generate_airport_dossier


def test_pdf_generates_file(sample_airport_stats, tmp_path):
    airport = sample_airport_stats[0]  # JFK
    output = tmp_path / "dossier_JFK.pdf"
    result = generate_airport_dossier(airport, sample_airport_stats, output_path=output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 1000  # sanity check: not empty


def test_pdf_uses_default_output_path(sample_airport_stats, tmp_path, monkeypatch):
    import reports.pdf as pdf_module
    monkeypatch.setattr(pdf_module, "OUTPUT_DIR", tmp_path)
    airport = sample_airport_stats[1]  # ORD
    result = generate_airport_dossier(airport, sample_airport_stats)
    assert result.exists()
    assert "ORD" in result.name


def test_pdf_handles_missing_species(sample_airport_stats, tmp_path):
    from data.models import AirportStats
    sparse = AirportStats(
        airport_id="TST", airport_name="Test Airport", state="TX",
        latitude=30.0, longitude=-90.0,
        total_strikes=5, damage_rate=0.0, avg_cost_per_strike=0.0,
        top_species=[],
        seasonal_counts={"Spring": 2, "Summer": 3, "Fall": 0, "Winter": 0},
        flyway="Central", risk_score=0.05,
    )
    output = tmp_path / "dossier_TST.pdf"
    result = generate_airport_dossier(sparse, sample_airport_stats, output_path=output)
    assert result.exists()
