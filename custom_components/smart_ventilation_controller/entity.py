"""Gemeinsame Basis aller Entitäten."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN
from .controller import SmartVentilationController


class SmartVentilationEntity(Entity):
    """Entität, die bei jeder Auswertung des Controllers aktualisiert wird."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: SmartVentilationController, description: EntityDescription) -> None:
        self.controller = controller
        self.entity_description = description
        entry = controller.entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Smart ventilation controller",
            model="Lüftung nach absoluter Feuchte",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))
