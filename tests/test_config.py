from __future__ import annotations

from pathlib import Path

import pytest

from src.config import DEFAULT_TOP_N, Config, load_config
from src.grouping import DEFAULT_PRECISION, DEFAULT_RADIUS_M, DEFAULT_STRATEGY


def test_defaults_when_nothing_supplied():
    config = load_config()
    assert config == Config(
        strategy=DEFAULT_STRATEGY,
        top_n=DEFAULT_TOP_N,
        radius_m=DEFAULT_RADIUS_M,
        precision=DEFAULT_PRECISION,
    )


def test_cli_overrides_applied():
    config = load_config(strategy="grid", top_n=5, radius_m=250.0, precision=3)
    assert (config.strategy, config.top_n, config.radius_m, config.precision) == (
        "grid",
        5,
        250.0,
        3,
    )


def test_none_overrides_are_ignored():
    config = load_config(strategy=None, top_n=None)
    assert config.strategy == DEFAULT_STRATEGY
    assert config.top_n == DEFAULT_TOP_N


def test_config_file_is_read(tmp_path: Path):
    path = tmp_path / "taxi.toml"
    path.write_text('strategy = "grid"\ntop = 7\nradius_m = 300\nprecision = 1\n')
    config = load_config(path)
    assert (config.strategy, config.top_n, config.radius_m, config.precision) == (
        "grid",
        7,
        300,
        1,
    )


def test_cli_overrides_config_file(tmp_path: Path):
    path = tmp_path / "taxi.toml"
    path.write_text('strategy = "grid"\ntop = 7\n')
    config = load_config(path, strategy="hotspot")
    assert config.strategy == "hotspot"  # CLI wins
    assert config.top_n == 7  # file value kept where no CLI override


def test_config_file_unknown_key_raises(tmp_path: Path):
    path = tmp_path / "taxi.toml"
    path.write_text('strategy = "grid"\nbogus = 1\n')
    with pytest.raises(ValueError):
        load_config(path)


def test_invalid_strategy_raises():
    with pytest.raises(ValueError):
        load_config(strategy="teleport")


def test_invalid_top_n_raises():
    with pytest.raises(ValueError):
        load_config(top_n=0)


def test_invalid_radius_raises():
    with pytest.raises(ValueError):
        load_config(radius_m=0.0)


def test_invalid_precision_raises():
    with pytest.raises(ValueError):
        load_config(precision=-1)
