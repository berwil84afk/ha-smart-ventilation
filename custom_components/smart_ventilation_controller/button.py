"""Button zum Wiederherstellen der Standard-Schwellwerte."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import SmartVentilationConfigEntry
from .entity import SmartVentilationEntity

RESTORE_DEFAULTS = ButtonEntityDescription(
    key="restore_defaults",
    translation_key="restore_defaults",
    icon="mdi:restore",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartVentilationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SmartVentilationRestoreButton(entry.runtime_data, RESTORE_DEFAULTS)])


class SmartVentilationRestoreButton(SmartVentilationEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.controller.async_restore_defaults()
