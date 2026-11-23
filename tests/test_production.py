"""English production defaults and real HA-service dashboard contracts."""

import json
from pathlib import Path

import pytest

from custom_components.philips_titanos.api import CannotConnect
from custom_components.philips_titanos.settings import (
    DEFAULT_OPTIONS,
    LEGACY_OPTIONS,
    option_enabled,
)
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

ROOT = Path(__file__).parents[1]
REMOTE = "remote.43pus8400_12"
PLAYER = "media_player.43pus8400_12"


@pytest.mark.parametrize("key,default", DEFAULT_OPTIONS.items())
def test_production_default_settings(key, default):
    """Normal writes are enabled, optional features/read trust are not."""
    assert option_enabled({}, key) is default
    assert option_enabled({key: not default}, key) is not default


@pytest.mark.parametrize("key,legacy", LEGACY_OPTIONS.items())
def test_optional_legacy_preference_and_new_precedence(key, legacy):
    """Preserve optional settings unless explicitly overridden in production."""
    assert option_enabled({legacy: True}, key) is True
    assert option_enabled({legacy: False}, key) is False
    assert option_enabled({legacy: True, key: False}, key) is False
    assert option_enabled({legacy: False, key: True}, key) is True


def test_bundled_option_keys_match_english_source():
    """Every locale must cover the option keys the English source defines."""
    directory = ROOT / "custom_components/philips_titanos/translations"
    english = json.loads((directory / "en.json").read_text())
    assert set(english["options"]["step"]["init"]["data"]) == (
        set(DEFAULT_OPTIONS) | {"broadcast"}
    )
    for translation in directory.glob("*.json"):
        data = json.loads(translation.read_text())
        assert set(data["options"]["step"]["init"]["data"]) == set(
            english["options"]["step"]["init"]["data"]
        ), translation.name


async def test_wol_opt_out_blocks_remote_and_media_feature(
    hass, config_entry, mock_client, mock_wake_on_lan
):
    hass.config_entries.async_update_entry(config_entry, options={"enable_wol": False})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    features = hass.states.get(PLAYER).attributes["supported_features"]
    assert not features & MediaPlayerEntityFeature.TURN_ON
    assert features & MediaPlayerEntityFeature.TURN_OFF
    with pytest.raises(ServiceValidationError, match="Wake-on-LAN is disabled"):
        await hass.services.async_call(
            "remote", "turn_on", {"entity_id": REMOTE}, blocking=True
        )
    mock_wake_on_lan.assert_not_awaited()
    mock_client.send_key.assert_not_awaited()


async def test_default_standby_timeout_remains_latched(hass, config_entry, mock_client):
    """Removing test mode must not introduce retrying an uncertain toggle."""
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    mock_client.send_key.side_effect = CannotConnect
    with pytest.raises(HomeAssistantError):
        await coordinator.async_turn_off()
    with pytest.raises(HomeAssistantError, match="already sent"):
        await coordinator.async_turn_off()
    mock_client.send_key.assert_awaited_once_with("Standby")


async def test_options_legacy_roundtrip_does_not_pair_or_write(
    hass, config_entry, mock_client, mock_wake_on_lan
):
    """Saving the new form retains optional preferences but discards test locks."""
    before = dict(config_entry.data)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            "keys_verified": False,
            "dial_verified": False,
            "powerstate_verified": True,
            "wol_verified": False,
        },
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options["enable_controls"] is True
    assert config_entry.options["enable_wol"] is True
    assert config_entry.options["enable_dial"] is False
    assert config_entry.options["trust_powerstate"] is True
    assert "keys_verified" not in config_entry.options
    assert config_entry.data == before
    mock_client.pair_request.assert_not_awaited()
    mock_client.send_key.assert_not_awaited()
    mock_wake_on_lan.assert_not_awaited()
