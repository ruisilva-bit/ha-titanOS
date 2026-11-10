"""Regressions for independent review findings."""

import json

import pytest

from custom_components.philips_titanos.api import PairingError, PairingSession
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .test_api import client_response


@pytest.mark.parametrize("value", [123, True, {}, [], None, ""])
async def test_grant_malformed_key(value):
    """A success envelope cannot store a malformed credential or escape the flow."""
    client, _ = client_response(json.dumps({"error_id": "SUCCESS", "auth_key": value}))
    with pytest.raises(PairingError, match="Invalid pairing credentials"):
        await client.pair_grant(
            PairingSession("test-device", "test-key", 42, 30), "1234"
        )
    assert client._auth is None


async def test_remote_disabled_by_default(
    hass, config_entry, mock_client, mock_wake_on_lan
):
    """No control writes or WOL before user opt-in, even via service calls."""
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    for service, extra in (
        ("send_command", {"command": "Home"}),
        ("send_command", {"command": "Standby"}),
        ("turn_off", {}),
        ("turn_on", {}),
    ):
        with pytest.raises((ServiceValidationError, HomeAssistantError)):
            await hass.services.async_call(
                "remote",
                service,
                {"entity_id": "remote.43pus8400_12", **extra},
                blocking=True,
            )
    mock_client.send_key.assert_not_awaited()
    mock_wake_on_lan.assert_not_awaited()


async def test_remote_explicit_test_mode(hass, config_entry, mock_client):
    """Testing is an explicit opt-in, not a claim of verified media controls."""
    hass.config_entries.async_update_entry(
        config_entry, options={"remote_testing": True}
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "remote",
        "send_command",
        {"entity_id": "remote.43pus8400_12", "command": "Home"},
        blocking=True,
    )
    mock_client.send_key.assert_awaited_once_with("Home")
    assert (
        hass.states.get("media_player.43pus8400_12").attributes["supported_features"]
        == 0
    )
