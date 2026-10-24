"""Sensoren: absolute Feuchte, Taupunkte, Laufzeit, Pause und Status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .controller import SmartVentilationConfigEntry, SmartVentilationController
from .entity import SmartVentilationEntity


@dataclass(frozen=True, kw_only=True)
class SmartVentilationSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SmartVentilationController], StateType | datetime]
    attrs_fn: Callable[[SmartVentilationController], dict[str, Any]] | None = None


def _reading(attr: str) -> Callable[[SmartVentilationController], float | None]:
    return lambda c: getattr(c.readings, attr) if c.readings else None


def _ah(key: str, name: str, attr: str, icon: str) -> SmartVentilationSensorDescription:
    return SmartVentilationSensorDescription(
        key=key,
        name=name,
        icon=icon,
        native_unit_of_measurement=CONCENTRATION_GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_reading(attr),
    )


def _dew_point(key: str, name: str, attr: str) -> SmartVentilationSensorDescription:
    return SmartVentilationSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_reading(attr),
    )


SENSORS: tuple[SmartVentilationSensorDescription, ...] = (
    _ah("ah_indoor", "Absolute Feuchte innen", "ah_indoor", "mdi:home-thermometer"),
    _ah("ah_outdoor", "Absolute Feuchte außen", "ah_outdoor", "mdi:weather-cloudy"),
    _ah("ah_difference", "Feuchtedifferenz", "difference", "mdi:water-sync"),
    _dew_point("dew_point_indoor", "Taupunkt innen", "dew_point_indoor"),
    _dew_point("dew_point_outdoor", "Taupunkt außen", "dew_point_outdoor"),
    SmartVentilationSensorDescription(
        key="runtime",
        name="Laufzeit",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda c: round(c.runtime.total_seconds() / 60) if c.runtime else 0,
    ),
    SmartVentilationSensorDescription(
        key="pause_until",
        name="Pause bis",
        icon="mdi:timer-pause",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.pause_until,
    ),
    SmartVentilationSensorDescription(
        key="status",
        name="Status",
        icon="mdi:fan-alert",
        value_fn=lambda c: c.status,
        attrs_fn=lambda c: {"code": c.status_code},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartVentilationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    async_add_entities(SmartVentilationSensor(controller, description) for description in SENSORS)


class SmartVentilationSensor(SmartVentilationEntity, SensorEntity):
    entity_description: SmartVentilationSensorDescription

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.controller)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.controller)
