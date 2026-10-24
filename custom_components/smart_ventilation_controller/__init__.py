"""Smart ventilation controller: Lüftung nach absoluter Luftfeuchtigkeit."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import SmartVentilationConfigEntry, SmartVentilationController

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> bool:
    controller = SmartVentilationController(hass, entry)
    await controller.async_load()
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    controller.async_start()
    entry.async_on_unload(controller.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: SmartVentilationConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
