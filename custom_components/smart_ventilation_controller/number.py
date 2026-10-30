"""Schwellwerte als Number-Entitäten (im Dashboard verstellbar)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    NUM_MIN_BATTERY,
    NUM_BUFFER_OFF,
    NUM_BUFFER_ON,
    NUM_DEWPOINT_MARGIN,
    NUM_MIN_HUMIDITY,
    UNIT_ABSOLUTE_HUMIDITY,
)
from .controller import SmartVentilationConfigEntry
from .entity import SmartVentilationEntity

NUMBERS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=NUM_BUFFER_ON,
        translation_key=NUM_BUFFER_ON,
        icon="mdi:water-plus",
        native_min_value=0,
        native_max_value=10,
        native_step=0.1,
        native_unit_of_measurement=UNIT_ABSOLUTE_HUMIDITY,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key=NUM_BUFFER_OFF,
        translation_key=NUM_BUFFER_OFF,
        icon="mdi:water-minus",
        native_min_value=0,
        native_max_value=10,
        native_step=0.1,
        native_unit_of_measurement=UNIT_ABSOLUTE_HUMIDITY,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key=NUM_DEWPOINT_MARGIN,
        translation_key=NUM_DEWPOINT_MARGIN,
        icon="mdi:thermometer-water",
        native_min_value=0,
        native_max_value=10,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key=NUM_MIN_HUMIDITY,
        translation_key=NUM_MIN_HUMIDITY,
        icon="mdi:water-percent",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)

# Nur bei Batteriebetrieb
BATTERY_NUMBERS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=NUM_MIN_BATTERY,
        translation_key=NUM_MIN_BATTERY,
        icon="mdi:battery-alert-variant-outline",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartVentilationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    descriptions = NUMBERS + (BATTERY_NUMBERS if controller.uses_battery else ())
    async_add_entities(
        SmartVentilationNumber(controller, description) for description in descriptions
    )


class SmartVentilationNumber(SmartVentilationEntity, NumberEntity):
    @property
    def native_value(self) -> float:
        return self.controller.values[self.entity_description.key]

    async def async_set_native_value(self, value: float) -> None:
        values = self.controller.values
        key = self.entity_description.key
        if (key == NUM_BUFFER_OFF and value > values[NUM_BUFFER_ON]) or (
            key == NUM_BUFFER_ON and value < values[NUM_BUFFER_OFF]
        ):
            raise ServiceValidationError(
                "Der Ausschalt-Puffer muss kleiner oder gleich dem Einschalt-Puffer sein."
            )
        await self.controller.async_set_value(key, value)
