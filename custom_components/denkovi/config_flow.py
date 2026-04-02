"""Config flow for the Denkovi integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_INVERT,
    CONF_PASSWORD,
    CONF_RELAY_NAME,
    CONF_RELAYS,
    CONF_RESOURCE,
    DEFAULT_PASSWORD,
    DOMAIN,
    MAX_RELAYS,
)

_LOGGER = logging.getLogger(__name__)


async def _test_connection(resource: str, password: str) -> dict | None:
    """Test connection and return current state JSON or None on failure."""
    url = f"{resource}/current_state.json?pw={password}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
    except Exception:
        _LOGGER.debug("Connection test to %s failed", resource, exc_info=True)
    return None


def _count_relays(data: dict) -> int:
    """Return the number of relays from the device response."""
    try:
        outputs = data["CurrentState"]["Output"]
        return len(outputs)
    except (KeyError, TypeError):
        return MAX_RELAYS


class DenkoviConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Denkovi."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._resource: str = ""
        self._password: str = DEFAULT_PASSWORD
        self._relay_count: int = MAX_RELAYS

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            resource = user_input[CONF_RESOURCE].rstrip("/")
            password = user_input[CONF_PASSWORD]

            data = await _test_connection(resource, password)
            if data is None:
                errors["base"] = "cannot_connect"
            else:
                self._resource = resource
                self._password = password
                self._relay_count = _count_relays(data)

                await self.async_set_unique_id(resource)
                self._abort_if_unique_id_configured()

                return await self.async_step_relays()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RESOURCE, default="http://"): str,
                    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_relays(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: select relays and assign names."""
        if user_input is not None:
            relays: dict[str, dict[str, Any]] = {}
            for i in range(1, self._relay_count + 1):
                key_enabled = f"relay_{i}_enabled"
                key_name = f"relay_{i}_name"
                key_invert = f"relay_{i}_invert"
                if user_input.get(key_enabled, False):
                    name = user_input.get(key_name, f"Relay {i}")
                    invert = user_input.get(key_invert, False)
                    relays[str(i)] = {CONF_RELAY_NAME: name, CONF_INVERT: invert}

            if not relays:
                return self.async_show_form(
                    step_id="relays",
                    data_schema=self._relays_schema(),
                    errors={"base": "no_relays_selected"},
                )

            return self.async_create_entry(
                title=f"Denkovi ({self._resource})",
                data={
                    CONF_RESOURCE: self._resource,
                    CONF_PASSWORD: self._password,
                },
                options={CONF_RELAYS: relays},
            )

        return self.async_show_form(
            step_id="relays",
            data_schema=self._relays_schema(),
        )

    def _relays_schema(self, current_relays: dict | None = None) -> vol.Schema:
        """Build the schema for relay selection."""
        fields: dict[Any, Any] = {}
        for i in range(1, self._relay_count + 1):
            existing = (current_relays or {}).get(str(i), {})
            is_enabled = bool(existing)
            name = existing.get(CONF_RELAY_NAME, f"Relay {i}")
            invert = existing.get(CONF_INVERT, False)

            fields[vol.Optional(f"relay_{i}_enabled", default=is_enabled)] = bool
            fields[vol.Optional(f"relay_{i}_name", default=name)] = str
            fields[vol.Optional(f"relay_{i}_invert", default=invert)] = bool
        return vol.Schema(fields)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return DenkoviOptionsFlow(config_entry)


class DenkoviOptionsFlow(OptionsFlow):
    """Handle options for Denkovi (change relay selection)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._relay_count: int = MAX_RELAYS

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the relay options."""
        resource = self._config_entry.data[CONF_RESOURCE]
        password = self._config_entry.data[CONF_PASSWORD]

        if self._relay_count == MAX_RELAYS:
            data = await _test_connection(resource, password)
            if data:
                self._relay_count = _count_relays(data)

        current_relays = self._config_entry.options.get(CONF_RELAYS, {})

        if user_input is not None:
            relays: dict[str, dict[str, Any]] = {}
            for i in range(1, self._relay_count + 1):
                key_enabled = f"relay_{i}_enabled"
                key_name = f"relay_{i}_name"
                key_invert = f"relay_{i}_invert"
                if user_input.get(key_enabled, False):
                    name = user_input.get(key_name, f"Relay {i}")
                    invert = user_input.get(key_invert, False)
                    relays[str(i)] = {CONF_RELAY_NAME: name, CONF_INVERT: invert}

            return self.async_create_entry(data={CONF_RELAYS: relays})

        fields: dict[Any, Any] = {}
        for i in range(1, self._relay_count + 1):
            existing = current_relays.get(str(i), {})
            is_enabled = bool(existing)
            name = existing.get(CONF_RELAY_NAME, f"Relay {i}")
            invert = existing.get(CONF_INVERT, False)

            fields[vol.Optional(f"relay_{i}_enabled", default=is_enabled)] = bool
            fields[vol.Optional(f"relay_{i}_name", default=name)] = str
            fields[vol.Optional(f"relay_{i}_invert", default=invert)] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
        )
