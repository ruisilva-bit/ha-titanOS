"""Additional concurrency and remote-command regression tests."""

import asyncio

import pytest

from custom_components.philips_titanos.api import ApiError
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


async def test_concurrent_standby(init_integration, mock_client):
    """Two HA callers cannot race and send the toggle twice."""
    coordinator = init_integration.runtime_data
    results = await asyncio.gather(
        coordinator.async_turn_off(),
        coordinator.async_turn_off(),
        return_exceptions=True,
    )
    assert sum(isinstance(result, HomeAssistantError) for result in results) == 1
    mock_client.send_key.assert_awaited_once_with("Standby")


async def test_remote_aliases_and_case(hass, init_integration, mock_client):
    """Aliases are explicit JointSpace keys; case cannot bypass the power guard."""

    async def send(commands):
        await hass.services.async_call(
            "remote",
            "send_command",
            {"entity_id": "remote.43pus8400_12", "command": commands, "delay_secs": 0},
            blocking=True,
        )

    await send(["up", "ok", "home"])
    assert [c.args[0] for c in mock_client.send_key.await_args_list] == [
        "CursorUp",
        "Confirm",
        "Home",
    ]
    mock_client.send_key.reset_mock()
    await send(["standby"])
    with pytest.raises(HomeAssistantError, match="already sent"):
        await send(["STANDBY"])
    mock_client.send_key.assert_awaited_once_with("Standby")
    with pytest.raises(ServiceValidationError, match="Unknown"):
        await send(["invented-key"])


async def test_optional_auth_is_not_unsupported(init_integration, mock_client):
    """Other optional endpoint errors do not get swallowed as unsupported."""
    coordinator = init_integration.runtime_data
    mock_client.get_power_state.side_effect = ApiError("GET", "/powerstate", 503)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert "powerstate" not in coordinator.optional_unavailable


async def test_pair_network_devices_optional(hass, mock_client):
    """A valid grant survives a forbidden optional network interface endpoint."""
    from custom_components.philips_titanos.const import DOMAIN

    mock_client.get_network_devices.side_effect = ApiError(
        "GET", "/network/devices", 403
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={"host": "192.0.2.10"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": "1234"}
    )
    assert result["type"] == "create_entry"
    assert result["data"]["auth_key"] == "granted"
    assert result["data"]["mac"] is None
