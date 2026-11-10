"""Capability options do not migrate or overwrite config-entry credentials."""

from homeassistant.data_entry_flow import FlowResultType


async def test_options(hass, config_entry, mock_client):
    """Save flags with a reload; preserve the paired device and auth key."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    before = dict(config_entry.data)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "keys_verified": True,
            "broadcast": "192.0.2.255",
            "powerstate_verified": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert dict(config_entry.data) == before
    assert config_entry.options["broadcast"] == "192.0.2.255"
    mock_client.pair_request.assert_not_awaited()
    assert hass.states.get("media_player.43pus8400_12").state == "unknown"


async def test_invalid_broadcast(hass, config_entry, mock_client):
    """Reject misconfigured UDP destinations before storing options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"broadcast": "not-an-ip"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_broadcast"}
