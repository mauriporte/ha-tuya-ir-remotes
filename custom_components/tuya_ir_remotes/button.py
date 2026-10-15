"""One button per key of each virtual remote."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IRData
from .api import IRKey, IRRemote


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: IRData = entry.runtime_data
    async_add_entities(IRKeyButton(data, remote, key) for remote in data.remotes for key in remote.keys)


class IRKeyButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"

    def __init__(self, data: IRData, remote: IRRemote, key: IRKey) -> None:
        self._data, self._remote, self._key = data, remote, key
        self._attr_unique_id = f"{remote.remote_id}_{key.key_id}"
        self._attr_name = key.name
        self._attr_device_info = data.device_info(remote)

    async def async_press(self) -> None:
        await self._data.press(self.hass, self._remote, self._key)
