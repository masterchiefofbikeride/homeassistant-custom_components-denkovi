"""Switch platform for the Denkovi integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import (
    CONF_INVERT,
    CONF_PASSWORD,
    CONF_RELAY_NAME,
    CONF_RELAYS,
    CONF_RESOURCE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Denkovi switches from a config entry."""
    resource = entry.data[CONF_RESOURCE]
    password = entry.data[CONF_PASSWORD]
    relays_config = entry.options.get(CONF_RELAYS, {})

    module = DenkoviModule(resource, password)
    await module.async_update()

    entities: list[DenkoviSwitch] = []
    for relay_num, relay_cfg in relays_config.items():
        name = relay_cfg.get(CONF_RELAY_NAME, f"Relay {relay_num}")
        invert = relay_cfg.get(CONF_INVERT, False)
        entities.append(
            DenkoviSwitch(module, entry.entry_id, name, relay_num, invert)
        )

    async_add_entities(entities, update_before_add=True)


class DenkoviModule:
    """Manages communication with a Denkovi relay board."""

    def __init__(self, resource: str, password: str) -> None:
        """Initialize."""
        self._resource = resource
        self._password = password
        self._state_data: dict | None = None

    @property
    def resource(self) -> str:
        """Return the base URL."""
        return self._resource

    async def async_turn_on_or_off(self, relay: str, payload: int) -> dict | None:
        """Send command and return updated state."""
        url = (
            f"{self._resource}/current_state.json"
            f"?pw={self._password}&Relay{relay}={payload}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        self._state_data = await resp.json(content_type=None)
                        return self._state_data
        except Exception:
            _LOGGER.error("Failed to send command to %s", self._resource)
        return None

    def get_relay_value(self, relay: str) -> int | None:
        """Return the current value (0 or 1) for a relay from cached state."""
        if self._state_data is None:
            return None
        try:
            return int(
                self._state_data["CurrentState"]["Output"][int(relay) - 1]["Value"]
            )
        except (KeyError, IndexError, TypeError, ValueError):
            _LOGGER.error("Unexpected state data structure")
            return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Fetch current state from the device."""
        url = f"{self._resource}/current_state.json?pw={self._password}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        self._state_data = await resp.json(content_type=None)
                    else:
                        _LOGGER.error(
                            "Unexpected HTTP %s from %s", resp.status, self._resource
                        )
        except Exception:
            _LOGGER.error("Connection error updating %s", self._resource)


class DenkoviSwitch(SwitchEntity):
    """A switch entity representing a single Denkovi relay."""

    _attr_has_entity_name = True

    def __init__(
        self,
        module: DenkoviModule,
        entry_id: str,
        name: str,
        relay: str,
        invert: bool,
    ) -> None:
        """Initialize."""
        self._module = module
        self._relay = relay
        self._invert = invert
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_relay_{relay}"
        self._attr_available = True

    @property
    def device_info(self):
        """Return device info to group entities under one device."""
        return {
            "identifiers": {(DOMAIN, self._module.resource)},
            "name": f"Denkovi ({self._module.resource})",
            "manufacturer": "Denkovi",
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the relay on."""
        payload = int(not self._invert)
        result = await self._module.async_turn_on_or_off(self._relay, payload)
        if result is not None:
            status_value = int(self._invert)
            val = self._module.get_relay_value(self._relay)
            self._attr_is_on = val is not None and val != status_value
            self._attr_available = True
        else:
            self._attr_available = False

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the relay off."""
        payload = int(self._invert)
        result = await self._module.async_turn_on_or_off(self._relay, payload)
        if result is not None:
            status_value = int(self._invert)
            val = self._module.get_relay_value(self._relay)
            self._attr_is_on = val is not None and val != status_value
            self._attr_available = True
        else:
            self._attr_available = False

    async def async_update(self) -> None:
        """Fetch state from the device."""
        try:
            await self._module.async_update()
            status_value = int(self._invert)
            val = self._module.get_relay_value(self._relay)
            if val is not None:
                self._attr_is_on = val != status_value
                self._attr_available = True
            else:
                self._attr_available = False
        except Exception:
            _LOGGER.error("Error updating relay %s", self._relay)
            self._attr_available = False

