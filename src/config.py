"""Resolve application settings from defaults, a config file, and CLI overrides.

Precedence (lowest to highest): built-in defaults, then an optional TOML config
file, then explicit command-line arguments. Validation happens once, in
:class:`Config`'s constructor, so the rest of the app consumes settings it can
trust.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.grouping import (
    DEFAULT_PRECISION,
    DEFAULT_RADIUS_M,
    DEFAULT_STRATEGY,
    STRATEGIES,
)

__all__ = ["DEFAULT_TOP_N", "Config", "load_config"]

DEFAULT_TOP_N = 10
_CONFIG_KEYS = frozenset({"strategy", "top_n", "radius_m", "precision"})


@dataclass(frozen=True)
class Config:
    """Validated grouping settings.

    Attributes:
        strategy: Grouping strategy, one of :data:`~src.grouping.STRATEGIES`.
        top_n: Number of areas to report.
        radius_m: Hotspot footprint radius in metres (``"hotspot"`` only).
        precision: Decimal places for the reported coordinate.
    """

    strategy: str = DEFAULT_STRATEGY
    top_n: int = DEFAULT_TOP_N
    radius_m: float = DEFAULT_RADIUS_M
    precision: int = DEFAULT_PRECISION

    def __post_init__(self) -> None:
        """Reject invalid settings at construction.

        Raises:
            ValueError: If any field is out of range or an unknown strategy.
        """
        if self.strategy not in STRATEGIES:
            raise ValueError(
                f"unknown strategy {self.strategy!r}; expected one of {STRATEGIES}"
            )
        if self.top_n < 1:
            raise ValueError(f"top_n must be >= 1, got {self.top_n}")
        if self.radius_m <= 0:
            raise ValueError(f"radius_m must be > 0, got {self.radius_m}")
        if self.precision < 0:
            raise ValueError(f"precision must be >= 0, got {self.precision}")


def load_config(
    config_path: Path | None = None,
    *,
    strategy: str | None = None,
    top_n: int | None = None,
    radius_m: float | None = None,
    precision: int | None = None,
) -> Config:
    """Build a :class:`Config` from defaults, a config file, and CLI overrides.

    Args:
        config_path: Optional path to a TOML config file.
        strategy: CLI override for the strategy, or ``None`` to defer.
        top_n: CLI override for the number of areas, or ``None``.
        radius_m: CLI override for the hotspot radius, or ``None``.
        precision: CLI override for coordinate precision, or ``None``.

    Returns:
        The resolved, validated configuration.

    Raises:
        ValueError: If the file has unknown keys or the result is invalid.
        FileNotFoundError: If ``config_path`` is given but does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    values: dict[str, Any] = {}
    if config_path is not None:
        values.update(_read_config_file(config_path))

    overrides = {
        "strategy": strategy,
        "top_n": top_n,
        "radius_m": radius_m,
        "precision": precision,
    }
    values.update({key: val for key, val in overrides.items() if val is not None})
    return Config(**values)


def _read_config_file(path: Path) -> dict[str, Any]:
    """Read and lightly validate a TOML config file.

    Accepts the keys ``strategy``, ``top``/``top_n``, ``radius_m``, and
    ``precision`` at the top level.

    Args:
        path: Path to the TOML file.

    Returns:
        A dict of recognised settings (``top`` normalised to ``top_n``).

    Raises:
        ValueError: If the file contains unrecognised keys.
    """
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    if "top" in data:
        data["top_n"] = data.pop("top")
    unknown = set(data) - _CONFIG_KEYS
    if unknown:
        raise ValueError(
            f"unknown config keys {sorted(unknown)}; expected {sorted(_CONFIG_KEYS)}"
        )
    return data
