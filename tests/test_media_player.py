# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Hardware-independent safety and HA service contract tests.

Modified for ha-titanOS; replaces optimistic Cast/channel tests from upstream.
"""

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import STATE_ON, STATE_UNKNOWN

ENTITY = "media_player.43pus8400_12"


async def call(hass, service, **data):
    """Exercise real registered HA services."""
    await hass.services.async_call(
        "media_player", service, {"entity_id": ENTITY, **data}, blocking=True
    )


async def test_verified_power_with_cast_closed(hass, init_integration, mock_client):
    """Validated power is independent of Cast and does not imply playback."""
    assert hass.states.get(ENTITY).state == STATE_ON
    assert not hass.states.get(ENTITY).attributes["supported_features"] & (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_SET
    )


async def test_defaults_follow_power_reading(hass, config_entry, mock_client):
    """Out of the box the TV state follows the power reading, which is trusted."""
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_ON
    assert hass.states.get(ENTITY).attributes["supported_features"] == (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
    )
    assert hass.states.get("light.43pus8400_12_ambilight") is None
    mock_client.get_power_state.assert_awaited()


async def test_unreadable_power_stays_unknown(hass, config_entry, mock_client):
    """An explicit opt-out returns to the conservative unknown state."""
    mock_client.get_power_state.return_value = None
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
