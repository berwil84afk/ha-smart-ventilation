"""Smart ventilation controller: Lüftung nach absoluter Luftfeuchtigkeit."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, NUM_MIN_BATTERY
from .controller import SmartVentilationConfigEntry, SmartVentilationController

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

# Entitäten, die es nur bei Batteriebetrieb gibt
BATTERY_ENTITIES = [(Platform.NUMBER, NUM_MIN_BATTERY), (Platform.BINARY_SENSOR, "battery_low")]


async def async_setup_entry(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> bool:
    controller = SmartVentilationController(hass, entry)
    await controller.async_load()
    entry.runtime_data = controller

    if not controller.uses_battery:
        _remove_battery_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    controller.async_start()
    entry.async_on_unload(controller.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_battery_entities(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> None:
    """Nach dem Wechsel auf Stromnetz verwaiste Batterie-Entitäten aus der Registry entfernen."""
    registry = er.async_get(hass)
    for platform, key in BATTERY_ENTITIES:
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}"):
            registry.async_remove(entity_id)


async def _async_update_listener(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
