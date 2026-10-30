"""Binärsensoren: Lüften sinnvoll, Kondensationsgefahr, Nachtruhe, Zwangspause, Ladezustand."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import SmartVentilationConfigEntry, SmartVentilationController
from .entity import SmartVentilationEntity


@dataclass(frozen=True, kw_only=True)
class SmartVentilationBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[SmartVentilationController], bool]


BINARY_SENSORS: tuple[SmartVentilationBinarySensorDescription, ...] = (
    SmartVentilationBinarySensorDescription(
        key="ventilation_useful",
        translation_key="ventilation_useful",
        icon="mdi:fan-chevron-up",
        value_fn=lambda c: c.ventilation_useful,
    ),
    SmartVentilationBinarySensorDescription(
        key="condensation_risk",
        translation_key="condensation_risk",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda c: c.condensation_risk,
    ),
    SmartVentilationBinarySensorDescription(
        key="night_active",
        translation_key="night_active",
        icon="mdi:weather-night",
        value_fn=lambda c: c.night_active,
    ),
    SmartVentilationBinarySensorDescription(
        key="pause_active",
        translation_key="pause_active",
        icon="mdi:timer-pause",
        value_fn=lambda c: c.pause_until is not None,
    ),
)

# Nur bei Batteriebetrieb; an, solange der Ladezustand das Lüften sperrt
BATTERY_BINARY_SENSORS: tuple[SmartVentilationBinarySensorDescription, ...] = (
    SmartVentilationBinarySensorDescription(
        key="battery_low",
        translation_key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda c: c.battery_blocked,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartVentilationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    descriptions = BINARY_SENSORS + (BATTERY_BINARY_SENSORS if controller.uses_battery else ())
    async_add_entities(
        SmartVentilationBinarySensor(controller, description) for description in descriptions
    )


class SmartVentilationBinarySensor(SmartVentilationEntity, BinarySensorEntity):
    entity_description: SmartVentilationBinarySensorDescription

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.controller)
