"""Schalter zum Ein-/Ausschalten der Automatik."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import SmartVentilationConfigEntry
from .entity import SmartVentilationEntity

AUTOMATIC = SwitchEntityDescription(key="automatic", translation_key="automatic", icon="mdi:fan-auto")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartVentilationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SmartVentilationAutomaticSwitch(entry.runtime_data, AUTOMATIC)])


class SmartVentilationAutomaticSwitch(SmartVentilationEntity, SwitchEntity):
    @property
    def is_on(self) -> bool:
        return self.controller.automatic

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_set_automatic(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_set_automatic(False)
