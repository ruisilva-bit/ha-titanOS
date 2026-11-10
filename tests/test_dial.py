"""Optional local DIAL transport and Home Assistant service tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.philips_titanos.api import ApiError, CannotConnect, TitanOSError
from custom_components.philips_titanos.dial import DialClient
from homeassistant.components.media_player import MediaPlayerEntityFeature


def dial_response(
    body=(
        b'<service xmlns="urn:dial-multiscreen-org:schemas:dial">'
        b"<state>stopped</state></service>"
    ),
    status=200,
):
    """Mock only the HTTP response, preserving method/headers/status handling."""
    response = AsyncMock()
    response.status = status
    response.content.read.return_value = body
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.request.return_value = context
    return DialClient(session, "192.0.2.10"), session


async def test_dial_get_state():
    """XML namespaces do not interfere with DIAL state reads."""
    client, session = dial_response()
    assert await client.get_state("YouTube") == "stopped"
    args, kwargs = session.request.call_args
    assert args == ("GET", "http://192.0.2.10:56789/apps/YouTube")
    assert kwargs["headers"] == {"Origin": "https://www.youtube.com"}
    assert kwargs["allow_redirects"] is False


async def test_dial_launch():
    """POST one documented app path, no cloud and no invented app identifiers."""
    client, session = dial_response(b"", 201)
    await client.launch("Netflix")
    assert session.request.call_args.args[0] == "POST"
    assert session.request.call_args.kwargs["headers"] == {
        "Origin": "https://www.netflix.com"
    }
    with pytest.raises(TitanOSError):
        await client.launch("invented-app")
    assert session.request.call_count == 1


@pytest.mark.parametrize(
    "body", [b"not-xml", b'<!DOCTYPE x [<!ENTITY x "boom">]><x>&x;</x>', b"x" * 65537]
)
async def test_dial_bad_xml(body):
    """Bound untrusted response bodies and reject XML entity declarations."""
    client, _ = dial_response(body)
    with pytest.raises(TitanOSError):
        await client.get_state("YouTube")


async def test_dial_http_and_timeout():
    """One POST only even if a timeout could hide successful execution."""
    client, session = dial_response(status=403)
    with pytest.raises(ApiError):
        await client.launch("YouTube")
    session.request.return_value.__aenter__.side_effect = TimeoutError
    with pytest.raises(CannotConnect):
        await client.launch("YouTube")
    assert session.request.call_count == 2


async def test_dial_ha_gated(hass, config_entry, mock_client):
    """Discover only on opt-in; actual HA service launches a detected registration."""
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "dial_verified": True}
    )
    dial = AsyncMock(spec=DialClient)
    dial.discover.return_value = ["YouTube"]
    with patch("custom_components.philips_titanos.DialClient", return_value=dial):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get("media_player.43pus8400_12")
    assert state.attributes["supported_features"] & MediaPlayerEntityFeature.PLAY_MEDIA
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": state.entity_id,
            "media_content_type": "app",
            "media_content_id": "YouTube",
        },
        blocking=True,
    )
    dial.launch.assert_awaited_once_with("YouTube")
    # Launch acknowledgements do not replace the foreground activity or power.
    assert config_entry.runtime_data.data.activity == "browser"
