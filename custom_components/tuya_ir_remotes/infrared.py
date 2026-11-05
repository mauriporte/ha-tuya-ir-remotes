"""The IR blaster as a Home Assistant infrared emitter, so IR integrations (LG, Samsung, Gree... Infrared) can send through it."""
from __future__ import annotations

from homeassistant.components.infrared import InfraredCommand, InfraredEmitterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, IRData, _raise_trial_issue
from .api import TrialExpired, TuyaError, ir_code

PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: IRData = entry.runtime_data
    if data.remotes:  # Tuya's send-code call needs a remote of this blaster in its path
        async_add_entities([TuyaInfraredEmitter(data)])


class TuyaInfraredEmitter(InfraredEmitterEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, data: IRData) -> None:
        self._data = data
        self._attr_unique_id = f"{data.hub_id}-emitter"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, data.hub_id)})

    async def async_send_command(self, command: InfraredCommand) -> None:
        try:
            await self._data.client.send_code(self._data.hub_id, self._data.remotes[0].remote_id, ir_code(command.get_raw_timings()))
        except TrialExpired as err:
            _raise_trial_issue(self.hass)
            raise HomeAssistantError("The Tuya cloud project's free trial has expired: extend it on platform.tuya.com") from err
        except TuyaError as err:
            raise HomeAssistantError(f"Tuya could not send the IR code: {err}") from err
