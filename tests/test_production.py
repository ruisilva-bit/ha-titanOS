"""English production defaults and real HA-service dashboard contracts."""

import json
from pathlib import Path

import pytest
import yaml

from custom_components.philips_titanos.api import CannotConnect
from custom_components.philips_titanos.settings import (
    DEFAULT_OPTIONS,
    LEGACY_OPTIONS,
    option_enabled,
)
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import CONF_MAC
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from tools.build_dashboard import build_card

ROOT = Path(__file__).parents[1]
REMOTE = "remote.43pus8400_12"
PLAYER = "media_player.43pus8400_12"


def walk_cards(card):
    """Walk nested native cards without assuming their layout."""
    yield card
    for child in card.get("cards", []):
        yield from walk_cards(child)


ACTIONS = [
    card["tap_action"]
    for card in walk_cards(build_card(REMOTE, PLAYER))
    if card.get("tap_action", {}).get("action") == "perform-action"
]


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


def test_all_bundled_locales_are_english():
    """English UI is selected even on the previously supported HA locales."""
    directory = ROOT / "custom_components/philips_titanos/translations"
    english = json.loads((directory / "en.json").read_text())
    assert set(english["options"]["step"]["init"]["data"]) == (
        set(DEFAULT_OPTIONS) | {"broadcast"}
    )
    for translation in directory.glob("*.json"):
        assert json.loads(translation.read_text()) == english


def test_example_matches_generator():
    """The shipped YAML is the tested generator output, not a stale sketch."""
    content = yaml.safe_load((ROOT / "examples/remote-card.yaml").read_text())
    assert content == build_card("remote.your_tv", "media_player.your_tv")
    for card in walk_cards(content):
        if card["type"] == "button":
            assert card["hold_action"] == {"action": "none"}
            assert card.get("double_tap_action", {"action": "none"}) == {
                "action": "none"
            }
    power = [a for a in ACTIONS if a["perform_action"] != "remote.send_command"]
    assert len(power) == 2
    assert all(a.get("confirmation") for a in power)


@pytest.mark.parametrize(
    "remote,player",
    [("light.tv", PLAYER), (REMOTE, "remote.tv"), ("remote.TV", PLAYER)],
)
def test_generator_rejects_invalid_entity_ids(remote, player):
    with pytest.raises(ValueError):
        build_card(remote, player)


@pytest.mark.parametrize("action", ACTIONS)
async def test_every_dashboard_button_uses_registered_ha_service(
    hass, config_entry, mock_client, mock_wake_on_lan, action
):
    """Exercise shipped button data through HA with only TV I/O mocked."""
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    domain, service = action["perform_action"].split(".")
    before = dict(config_entry.data)
    await hass.services.async_call(
        domain,
        service,
        {**action["target"], **action.get("data", {})},
        blocking=True,
    )
    if service == "send_command":
        mock_client.send_key.assert_awaited_once_with(action["data"]["command"][0])
    elif service == "turn_off":
        mock_client.send_key.assert_awaited_once_with("Standby")
    else:
        mock_wake_on_lan.assert_awaited_once_with(before[CONF_MAC], "255.255.255.255")
        mock_client.send_key.assert_not_awaited()
    assert config_entry.data == before
    mock_client.pair_request.assert_not_awaited()
    mock_client.pair_grant.assert_not_awaited()
    mock_client.get_power_state.assert_not_awaited()
    assert hass.states.get(PLAYER).state == "unknown"


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
