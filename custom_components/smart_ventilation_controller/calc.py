"""Feuchte-Berechnungen (Magnus-Formel, wie in der ursprünglichen Automation)."""

from __future__ import annotations

import math


def saturation_vapor_pressure(temp_c: float) -> float:
    """Sättigungsdampfdruck in hPa."""
    return 6.1078 * 10 ** ((7.5 * temp_c) / (237.3 + temp_c))


def absolute_humidity(temp_c: float, rel_humidity: float) -> float:
    """Absolute Feuchte in g/m³."""
    vapor_pressure = rel_humidity / 100 * saturation_vapor_pressure(temp_c)
    return 216.7 * vapor_pressure / (273.15 + temp_c)


def dew_point(temp_c: float, rel_humidity: float) -> float:
    """Taupunkt in °C."""
    vapor_pressure = rel_humidity / 100 * saturation_vapor_pressure(temp_c)
    v = math.log10(vapor_pressure / 6.1078)
    return 237.3 * v / (7.5 - v)
