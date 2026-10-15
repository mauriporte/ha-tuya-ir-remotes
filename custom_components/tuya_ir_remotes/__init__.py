"""Tuya IR Remotes: the virtual IR remotes of a Tuya IR blaster as Home Assistant buttons and remotes."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import Platform

from .api import AuthError, IRKey, IRRemote, TrialExpired, TuyaError, TuyaIRClient

DOMAIN = "tuya_ir_remotes"
PLATFORMS = [Platform.BUTTON, Platform.REMOTE]
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DATA_CENTER = "data_center"
CONF_HUB_ID = "hub_id"
CONF_HUB_NAME = "hub_name"
TRIAL_ISSUE = "trial_expired"
_LOGGER = logging.getLogger(__name__)


@dataclass
class IRData:
    client: TuyaIRClient
    hub_id: str
    hub_name: str
    remotes: list[IRRemote]

    def device_info(self, remote: IRRemote) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, remote.remote_id)},
            name=remote.name,
            manufacturer=remote.brand or "Tuya",
            model="Virtual IR remote",
            via_device=(DOMAIN, self.hub_id),
        )

    async def press(self, hass: HomeAssistant, remote: IRRemote, key: IRKey) -> None:
        try:
            await self.client.press(self.hub_id, remote, key)
        except TrialExpired as err:
            _raise_trial_issue(hass)
            raise HomeAssistantError("The Tuya cloud project's free trial has expired: extend it on platform.tuya.com") from err
        except TuyaError as err:
            raise HomeAssistantError(f"Tuya could not send '{key.name}' to {remote.name}: {err}") from err
        ir.async_delete_issue(hass, DOMAIN, TRIAL_ISSUE)


def _raise_trial_issue(hass: HomeAssistant) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        TRIAL_ISSUE,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=TRIAL_ISSUE,
        learn_more_url="https://platform.tuya.com/cloud/products",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    d = entry.data
    client = TuyaIRClient(async_get_clientsession(hass), d[CONF_ACCESS_ID], d[CONF_ACCESS_SECRET], d[CONF_DATA_CENTER])
    try:
        remotes = await client.remotes(d[CONF_HUB_ID])
    except TrialExpired as err:
        _raise_trial_issue(hass)
        raise ConfigEntryNotReady("The Tuya cloud project's free trial has expired") from err
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except TuyaError as err:
        raise ConfigEntryNotReady(str(err)) from err
    ir.async_delete_issue(hass, DOMAIN, TRIAL_ISSUE)
    dr.async_get(hass).async_get_or_create(  # parent of the remote devices (via_device)
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, d[CONF_HUB_ID])},
        name=d.get(CONF_HUB_NAME, "IR hub"),
        manufacturer="Tuya",
        model="IR blaster",
    )
    entry.runtime_data = IRData(client, d[CONF_HUB_ID], d.get(CONF_HUB_NAME, "IR hub"), remotes)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
