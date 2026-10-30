"""Einrichtungs- und Optionsdialoge des Smart ventilation controller."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ADDITIONAL_FANS,
    CONF_BATTERY_LEVEL,
    CONF_FAN,
    CONF_INDOOR_HUM,
    CONF_INDOOR_TEMP,
    CONF_MAX_RUNTIME,
    CONF_NIGHT_ENABLED,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_NOTIFY_ENTITIES,
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_SERVICES,
    CONF_OUTDOOR_HUM,
    CONF_OUTDOOR_TEMP,
    CONF_PAUSE,
    CONF_POWER_SOURCE,
    CONF_WALL_TEMP,
    DEFAULT_OPTIONS,
    DOMAIN,
    EVENTS,
    POWER_BATTERY,
    POWER_GRID,
    POWER_SOURCES,
)

FAN_DOMAINS = ["switch", "fan", "light", "input_boolean"]


def _sensor_schema() -> vol.Schema:
    sensor = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    return vol.Schema(
        {
            vol.Required(CONF_INDOOR_TEMP): sensor,
            vol.Required(CONF_INDOOR_HUM): sensor,
            vol.Required(CONF_OUTDOOR_TEMP): sensor,
            vol.Required(CONF_OUTDOOR_HUM): sensor,
            vol.Optional(CONF_WALL_TEMP): sensor,
            vol.Required(CONF_FAN): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=FAN_DOMAINS)
            ),
            vol.Optional(CONF_ADDITIONAL_FANS, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=FAN_DOMAINS, multiple=True)
            ),
            vol.Required(CONF_POWER_SOURCE, default=POWER_GRID): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=POWER_SOURCES,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=CONF_POWER_SOURCE,
                )
            ),
            vol.Optional(CONF_BATTERY_LEVEL): sensor,
        }
    )


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Batterie braucht einen Ladezustand-Sensor; beim Stromnetz wird er verworfen."""
    if user_input.get(CONF_POWER_SOURCE) != POWER_BATTERY:
        user_input.pop(CONF_BATTERY_LEVEL, None)
        return {}
    if not user_input.get(CONF_BATTERY_LEVEL):
        return {CONF_BATTERY_LEVEL: "battery_level_required"}
    return {}


def _minutes_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=1440,
            step=5,
            unit_of_measurement="min",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class SmartVentilationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung: Name, Sensoren und Lüfter."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SmartVentilationOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := _validate(user_input)):
                await self.async_set_unique_id(user_input[CONF_FAN])
                self._abort_if_unique_id_configured()
                title = user_input.pop(CONF_NAME)
                return self.async_create_entry(
                    title=title, data=user_input, options=dict(DEFAULT_OPTIONS)
                )

        default_name = "Keller" if self.hass.config.language.startswith("de") else "Basement"
        schema = vol.Schema({vol.Required(CONF_NAME, default=default_name): str}).extend(
            _sensor_schema().schema
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := _validate(user_input)):
                return self.async_update_reload_and_abort(
                    entry, unique_id=user_input[CONF_FAN], data=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _sensor_schema(), user_input or entry.data
            ),
            errors=errors,
        )


class SmartVentilationOptionsFlow(OptionsFlow):
    """Optionen: Laufzeit, Pause, Nachtruhe, Benachrichtigungen."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        legacy_notify = sorted(
            service
            for service in self.hass.services.async_services().get("notify", {})
            if service not in ("send_message", "persistent_notification")
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_MAX_RUNTIME): _minutes_selector(),
                vol.Required(CONF_PAUSE): _minutes_selector(),
                vol.Required(CONF_NIGHT_ENABLED): selector.BooleanSelector(),
                vol.Required(CONF_NIGHT_START): selector.TimeSelector(),
                vol.Required(CONF_NIGHT_END): selector.TimeSelector(),
                vol.Optional(CONF_NOTIFY_ENTITIES, default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify", multiple=True)
                ),
                vol.Optional(CONF_NOTIFY_SERVICES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=legacy_notify,
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_NOTIFY_EVENTS, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=EVENTS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_NOTIFY_EVENTS,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, {**DEFAULT_OPTIONS, **self.config_entry.options}
            ),
        )
