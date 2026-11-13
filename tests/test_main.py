from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import EXIT_ERROR, main

FIXTURE = Path(__file__).parent / "fixtures" / "taxi_availability_sample.json"


def test_missing_source_file_returns_error(capsys: pytest.CaptureFixture[str]):
    code = main(["--source", "does-not-exist.json"])
    assert code == EXIT_ERROR
    assert "Error:" in capsys.readouterr().err


def test_malformed_data_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    # Valid JSON, but taxi_count disagrees with the coordinates -> TaxiDataError.
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "geometry": {
                            "type": "MultiPoint",
                            "coordinates": [[103.99, 1.36]],
                        },
                        "properties": {"taxi_count": 99, "timestamp": None},
                    }
                ],
            }
        )
    )
    code = main(["--source", str(bad)])
    assert code == EXIT_ERROR
    assert "Error:" in capsys.readouterr().err


def test_unknown_config_key_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    cfg = tmp_path / "taxi.toml"
    cfg.write_text('strategy = "grid"\nbogus = 1\n')
    code = main(["--source", str(FIXTURE), "--config", str(cfg)])
    assert code == EXIT_ERROR
    assert "Error:" in capsys.readouterr().err


def test_missing_config_file_returns_error(capsys: pytest.CaptureFixture[str]):
    code = main(["--source", str(FIXTURE), "--config", "no-such.toml"])
    assert code == EXIT_ERROR
    assert "Error:" in capsys.readouterr().err
