"""The IR blaster as a Home Assistant infrared emitter (HA 2026.x+). Run: pip install pytest-homeassistant-custom-component infrared-protocols"""
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")
pytest.importorskip("infrared_protocols")
from infrared_protocols.commands.nec import NECCommand  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from homeassistant.components.infrared import async_send_command  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402

from custom_components.tuya_ir_remotes.api import IRKey, IRRemote, ir_code  # noqa: E402

DATA = {"access_id": "id", "access_secret": "secret", "data_center": "eu", "hub_id": "hub1", "hub_name": "IR hub"}
CLIENT = "custom_components.tuya_ir_remotes.api.TuyaIRClient"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup(hass, remotes):
    entry = MockConfigEntry(domain="tuya_ir_remotes", title="IR hub", unique_id="hub1", data=DATA)
    entry.add_to_hass(hass)
    with patch(f"{CLIENT}.remotes", AsyncMock(return_value=remotes)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_blaster_sends_any_ir_command_through_tuya(hass):
    entry = await _setup(hass, [IRRemote("r1", "TV", 2, "LG", [IRKey("Power", 1, "Power")])])
    ents = [e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if e.domain == "infrared"]
    assert len(ents) == 1
    cmd = NECCommand(address=0x04, command=0x08)
    with patch(f"{CLIENT}.send_code", AsyncMock()) as send:
        await async_send_command(hass, ents[0].entity_id, cmd)
    send.assert_awaited_once_with("hub1", "r1", ir_code(cmd.get_raw_timings()))
    assert hass.states.get(ents[0].entity_id).state not in ("unknown", "unavailable")  # time of the last command


async def test_no_emitter_without_a_remote(hass):
    entry = await _setup(hass, [])  # Tuya's send call needs one of the blaster's remotes in its path
    assert not [e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if e.domain == "infrared"]
