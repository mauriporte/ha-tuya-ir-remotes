from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import CONF_ACCESS_ID, CONF_ACCESS_SECRET, CONF_DATA_CENTER, CONF_HUB_ID, CONF_HUB_NAME, DOMAIN
from .api import DATA_CENTERS, AuthError, TrialExpired, TuyaError, TuyaIRClient

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_ID): str,
        vol.Required(CONF_ACCESS_SECRET): str,
        vol.Required(CONF_DATA_CENTER, default="eu"): vol.In(list(DATA_CENTERS)),
    }
)


def _error(err: TuyaError) -> str:
    if isinstance(err, TrialExpired):
        return "trial_expired"
    if isinstance(err, AuthError):
        return "invalid_auth"
    return "cannot_connect"


class TuyaIRRemotesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict = {}
        self._hubs: dict[str, str] = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = TuyaIRClient(
                async_get_clientsession(self.hass),
                user_input[CONF_ACCESS_ID],
                user_input[CONF_ACCESS_SECRET],
                user_input[CONF_DATA_CENTER],
            )
            try:
                hubs = await client.find_hubs()
            except TuyaError as err:
                errors["base"] = _error(err)
            else:
                if not hubs:
                    errors["base"] = "no_hubs"
                else:
                    self._creds = user_input
                    self._hubs = dict(hubs)
                    if len(hubs) == 1:
                        return await self._create(hubs[0][0])
                    return await self.async_step_hub()
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_hub(self, user_input=None):
        if user_input is not None:
            return await self._create(user_input[CONF_HUB_ID])
        return self.async_show_form(step_id="hub", data_schema=vol.Schema({vol.Required(CONF_HUB_ID): vol.In(self._hubs)}))

    async def _create(self, hub_id: str):
        await self.async_set_unique_id(hub_id)
        self._abort_if_unique_id_configured()
        name = self._hubs[hub_id]
        return self.async_create_entry(title=name, data={**self._creds, CONF_HUB_ID: hub_id, CONF_HUB_NAME: name})

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            client = TuyaIRClient(async_get_clientsession(self.hass), data[CONF_ACCESS_ID], data[CONF_ACCESS_SECRET], data[CONF_DATA_CENTER])
            try:
                await client.remotes(data[CONF_HUB_ID])
            except TuyaError as err:
                errors["base"] = _error(err)
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_ID): str, vol.Required(CONF_ACCESS_SECRET): str}),
            errors=errors,
        )
