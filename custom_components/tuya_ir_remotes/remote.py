"""One remote entity per virtual remote, for remote.send_command in automations and scripts."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import ATTR_DELAY_SECS, ATTR_NUM_REPEATS, DEFAULT_DELAY_SECS, RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IRData
from .api import IRRemote


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: IRData = entry.runtime_data
    async_add_entities(IRRemoteEntity(data, remote) for remote in data.remotes)


class IRRemoteEntity(RemoteEntity):
    """IR is one-way: the device's real state is unknown, so this entity is always 'on' and only sends keys."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on = True
    _attr_assumed_state = True

    def __init__(self, data: IRData, remote: IRRemote) -> None:
        self._data, self._remote = data, remote
        self._attr_unique_id = remote.remote_id
        self._attr_device_info = data.device_info(remote)
        self._attr_extra_state_attributes = {"commands": [k.name for k in remote.keys]}

    def _find(self, command: str):
        wanted = command.casefold()
        key = next((k for k in self._remote.keys if k.name.casefold() == wanted or k.key == command), None)
        if key is None:
            raise ServiceValidationError(
                f"{self._remote.name} has no key '{command}'. Keys: {', '.join(k.name for k in self._remote.keys)}"
            )
        return key

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        keys = [self._find(c) for c in command]  # validate everything before sending anything
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for i in range(repeats):
            for j, key in enumerate(keys):
                if i or j:
                    await asyncio.sleep(delay)
                await self._data.press(self.hass, self._remote, key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Nothing to switch: use send_command with the remote's power key."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Nothing to switch: use send_command with the remote's power key."""
