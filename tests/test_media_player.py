# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Hardware-independent safety and HA service contract tests.

Modified for ha-titanOS; replaces optimistic Cast/channel tests from upstream.
"""

import pytest

from custom_components.philips_titanos.api import ApiError, CannotConnect
from custom_components.philips_titanos.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.philips_titanos.power import PowerState
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError

ENTITY = "media_player.43pus8400_12"


async def call(hass, service, **data):
    """Exercise real registered HA services."""
    await hass.services.async_call(
        "media_player", service, {"entity_id": ENTITY, **data}, blocking=True
    )


async def test_verified_power_with_cast_closed(hass, init_integration, mock_client):
    """Validated power is independent of Cast and does not imply playback."""
    assert hass.states.get(ENTITY).state == STATE_ON
    mock_client.is_on.assert_not_awaited()
    assert not hass.states.get(ENTITY).attributes["supported_features"] & (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_SET
    )
    mock_client.get_channel_db.assert_not_awaited()


async def test_safe_defaults(hass, config_entry, mock_client):
    """Reachable API plus activity must remain unknown without validated power."""
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    assert hass.states.get(ENTITY).attributes["supported_features"] == 0
    assert hass.states.get("light.43pus8400_12_ambilight") is None
    mock_client.get_power_state.assert_not_awaited()
    mock_client.is_on.assert_not_awaited()


@pytest.mark.parametrize(
    "service,key", [("volume_up", "VolumeUp"), ("volume_down", "VolumeDown")]
)
async def test_volume(hass, init_integration, mock_client, service, key):
    """Service dispatch proves the payload, not physical execution."""
    await call(hass, service)
    mock_client.send_key.assert_awaited_once_with(key)


async def test_standby_unknown_and_duplicate_guard(hass, init_integration, mock_client):
    """Do not discard Standby with closed Cast; do not retry an unconfirmed toggle."""
    coordinator = init_integration.runtime_data
    coordinator.power.observe(None)
    await coordinator.async_turn_off()
    mock_client.send_key.assert_awaited_once_with("Standby")
    assert coordinator.power.state == PowerState.STANDBY_PENDING
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    with pytest.raises(HomeAssistantError, match="already sent"):
        await coordinator.async_turn_off()
    mock_client.send_key.assert_awaited_once()


async def test_standby_failure_is_latched(hass, init_integration, mock_client):
    """A write timeout is ambiguous; retrying a toggle could wake the screen."""
    coordinator = init_integration.runtime_data
    mock_client.send_key.side_effect = CannotConnect
    with pytest.raises(HomeAssistantError):
        await coordinator.async_turn_off()
    with pytest.raises(HomeAssistantError, match="already sent"):
        await coordinator.async_turn_off()
    assert mock_client.send_key.await_count == 1


async def test_no_standby_when_disconnected(init_integration, mock_client):
    """A failed preflight cannot dispatch a toggle."""
    mock_client.get_current_activity.side_effect = CannotConnect
    with pytest.raises(HomeAssistantError):
        await init_integration.runtime_data.async_turn_off()
    mock_client.send_key.assert_not_awaited()


async def test_wol_records_intent_only(hass, init_integration, mock_wake_on_lan):
    """A UDP send is not a confirmed powered-on screen."""
    coordinator = init_integration.runtime_data
    await call(hass, "turn_on")
    mock_wake_on_lan.assert_awaited_once_with("02:00:00:00:00:01", "255.255.255.255")
    assert coordinator.power.state == PowerState.WAKING
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    await call(hass, "turn_on")
    assert mock_wake_on_lan.await_count == 1


async def test_recovery_and_backoff(hass, init_integration, mock_client):
    """Failure becomes unavailable, recovery resets backoff without re-pairing."""
    coordinator = init_integration.runtime_data
    mock_client.get_current_activity.side_effect = CannotConnect
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    assert coordinator.update_interval.total_seconds() == 60
    await coordinator.async_refresh()
    assert coordinator.update_interval.total_seconds() == 120
    mock_client.get_current_activity.side_effect = None
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY).state == STATE_ON
    assert coordinator.update_interval.total_seconds() == 30
    mock_client.pair_request.assert_not_awaited()


async def test_optional_unsupported_cached(init_integration, mock_client):
    """One unavailable optional endpoint cannot make the whole TV fail."""
    coordinator = init_integration.runtime_data
    mock_client.get_power_state.side_effect = ApiError("GET", "/powerstate", 404)
    await coordinator.async_refresh()
    count = mock_client.get_power_state.await_count
    await coordinator.async_refresh()
    assert mock_client.get_power_state.await_count == count
    assert coordinator.data.is_on is None
    assert coordinator.last_update_success


async def test_mute_no_optimism(hass, init_integration, mock_client):
    """HTTP success must not forge the resulting mute value."""
    await call(hass, "volume_mute", is_volume_muted=True)
    mock_client.send_key.assert_awaited_once_with("Mute")
    assert hass.states.get(ENTITY).attributes["is_volume_muted"] is False


async def test_reload_preserves_pairing(hass, init_integration, mock_client):
    """Reload reuses config-entry credentials and never requests a new PIN."""
    before = dict(init_integration.data)
    assert await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert dict(init_integration.data) == before
    mock_client.pair_request.assert_not_awaited()
    mock_client.pair_grant.assert_not_awaited()


async def test_diagnostics_allowlist(hass, init_integration):
    """Diagnostics must not expose even fake credentials, host, serial or MAC."""
    data = await async_get_config_entry_diagnostics(hass, init_integration)
    assert data["connected"]
    assert data["protocol"] == "jointspace_v6_https_digest"
    text = str(data)
    for value in ("granted", "0123456789abcdef", "192.0.2.10", "02:00:00:00:00:01"):
        assert value not in text
